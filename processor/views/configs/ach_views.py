from rest_framework.views import APIView
from rest_framework import status
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.http import HttpResponse, FileResponse
from django.db.models import Q, Sum
from django.db import transaction
from datetime import datetime, date
from decimal import Decimal
import logging
import json
from io import BytesIO
from user_app.serializers import AchGarnishmentConfigSerializer
from user_app.models import AchGarnishmentConfig
from django.shortcuts import get_object_or_404
from user_app.models import GarnishmentOrder, PayeeDetails
from user_app.models.ach import ACHFile
from processor.models.garnishment_result.result import GarnishmentResult
from processor.garnishment_library import ResponseHelper

logger = logging.getLogger(__name__)

class ACHFileGenerationView(APIView):
    """
    API view for generating ACH files in CCD+ format (NACHA compliant) for Child Support and FTB payments.
    Supports generating ACH files with Addenda Records and multiple export formats.
    """

    def _pad_string(self, value, length, align='left', fill_char=' '):
        """Pad string to specified length."""
        if value is None:
            value = ''
        value = str(value)[:length]
        if align == 'left':
            return value.ljust(length, fill_char)
        else:
            return value.rjust(length, fill_char)

    def _pad_number(self, value, length, fill_char='0'):
        """Pad number to specified length with leading zeros."""
        if value is None:
            value = 0
        return str(int(value)).rjust(length, fill_char)

    def _format_amount(self, amount, length=10):
        """Format amount as integer (cents) with leading zeros."""
        if amount is None:
            amount = Decimal('0.00')
        cents = int(amount * 100)
        return str(cents).rjust(length, '0')

    def _format_date(self, date_obj, format_type='yymmdd'):
        """Format date according to NACHA specifications."""
        # Ensure date_obj is a date object, not a string or datetime
        if date_obj is None:
            date_obj = date.today()
        elif isinstance(date_obj, str):
            try:
                date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
            except ValueError:
                date_obj = date.today()
        elif isinstance(date_obj, datetime):
            date_obj = date_obj.date()
        elif not isinstance(date_obj, date):
            date_obj = date.today()
        
        if format_type == 'yymmdd':
            return date_obj.strftime('%y%m%d')
        elif format_type == 'yyddd':
            return date_obj.strftime('%y%j')  # Julian date
        return date_obj.strftime('%y%m%d')

    def _generate_file_header(self, immediate_destination, immediate_origin, 
                              file_id_modifier='A', creation_date=None, creation_time=None,
                              immediate_destination_name="", immediate_origin_name="", batch_number=1):
        """
        Generate File Header Record (Type 1) with exact field positions per CSV specification.
        Position 1: Record Type Code (1)
        Position 2-3: Priority Code (01)
        Position 4-13: Immediate Receiving (10 digits, right-justified, space-filled)
        Position 14-23: Immediate Origin (10 digits, left-justified, space-filled)
        Position 24-29: File Creation Date (YYMMDD)
        Position 30-33: File Creation Time (HHMM)
        Position 34: File ID Modifier (A-Z, 0-9)
        Position 35-37: Record Size (094)
        Position 38-39: Blocking Factor (10)
        Position 40: Format Code (1)
        Position 41-63: Immediate Destination Name (23 chars, left-justified, space-filled)
        Position 64-86: Immediate Origin Name / Reference Code (23 chars, left-justified, space-filled)
        Position 87-94: Internal Reference Code (8 digits: Date + Batch Number)
        """
        if creation_date is None:
            creation_date = date.today()
        # Ensure creation_date is a date object, not a string
        elif isinstance(creation_date, str):
            try:
                creation_date = datetime.strptime(creation_date, '%Y-%m-%d').date()
            except ValueError:
                creation_date = date.today()
        elif not isinstance(creation_date, (date, datetime)):
            creation_date = date.today()
        elif isinstance(creation_date, datetime):
            creation_date = creation_date.date()
        
        if creation_time is None:
            creation_time = datetime.now().time()

        # Generate Internal Reference Code: Date (YYMMDD) + Batch Number (2 digits)
        internal_ref = self._format_date(creation_date) + self._pad_number(batch_number, 2)

        record = "1"  # Position 1: Record Type Code
        record += "01"  # Position 2-3: Priority Code
        record += self._pad_string(immediate_destination, 10, 'right', ' ')  # Position 4-13: Immediate Receiving
        record += self._pad_string(immediate_origin, 10, 'left', ' ')  # Position 14-23: Immediate Origin
        record += self._format_date(creation_date)  # Position 24-29: File Creation Date (YYMMDD)
        record += creation_time.strftime('%H%M')  # Position 30-33: File Creation Time (HHMM)
        record += file_id_modifier  # Position 34: File ID Modifier
        record += "094"  # Position 35-37: Record Size
        record += "10"  # Position 38-39: Blocking Factor
        record += "1"  # Position 40: Format Code
        # Convert to uppercase
        immediate_destination_name = str(immediate_destination_name).upper() if immediate_destination_name else ""
        immediate_origin_name = str(immediate_origin_name).upper() if immediate_origin_name else ""
        
        record += self._pad_string(immediate_destination_name, 23, 'left', ' ')  # Position 41-63: Immediate Destination Name
        record += self._pad_string(immediate_origin_name, 23, 'left', ' ')  # Position 64-86: Immediate Origin Name
        record += internal_ref  # Position 87-94: Internal Reference Code (8 digits)
        
        # Ensure record is exactly 94 characters (excluding newline)
        if len(record) != 94:
            record = record[:94].ljust(94, ' ')
        
        record += "\n"  # Newline
        return record

    def _generate_batch_header(self, batch_number, company_name, company_id, 
                              pay_date, company_discretionary_data="",
                              standard_entry_class="CCD", company_entry_description="",
                              originating_dfi_id="", service_class_code="200"):
        """
        Generate Batch Header Record (Type 5) for CCD+ format per CSV specification.
        Position 1: Record Type Code (5)
        Position 2-4: Service Class Code (200, 220, 225, etc.)
          * 200 = Mixed debits and credits
          * 220 = Credits only
          * 225 = Debits only
        Position 5-20: Company Name (16 chars)
        Position 21-40: Blank (20 chars)
        Position 41-50: Company Identification (10 digits)
        Position 51-53: Standard Entry Class Code (CCD)
        Position 54-63: Company Entry Description (10 chars)
        Position 64-69: Company Descriptive Date (6 digits, YYMMDD)
        Position 70-75: Effective Entry Date (6 digits, YYMMDD)
        Position 76-78: Blank (3 chars)
        Position 79: Originator Status Code (1)
        Position 80-87: Trace Record Part 1 - Originating DFI ID (8 digits)
        Position 88-94: Trace Record Part 2 - Batch Number (7 digits)
        
        Args:
            batch_number: Batch number (7 digits)
            company_name: Company name (max 16 chars)
            company_id: Company identification (10 digits)
            effective_date: Effective entry date (date object)
            company_discretionary_data: Company discretionary data (optional)
            standard_entry_class: Standard Entry Class code (default: "CCD")
            company_entry_description: Company entry description (default: "CHILD SUPP")
            originating_dfi_id: Originating DFI identification (8 digits)
            service_class_code: Service Class Code (default: "200")
        
        Returns:
            str: Formatted batch header record (94 characters + newline)
        """
        if  pay_date is None:
            pay_date = date.today()
        # Ensure effective_date is a date object, not a string
        elif isinstance(pay_date, str):
            try:
                pay_date = datetime.strptime(pay_date, '%Y-%m-%d').date()
            except ValueError:
                pay_date = date.today()
        elif not isinstance(pay_date, (date, datetime)):
            pay_date = date.today()
        elif isinstance(pay_date, datetime):
            pay_date = pay_date.date()
        
        if not company_entry_description:
            company_entry_description = "CHILD SUPP"

        # Convert to uppercase
        company_name = str(company_name).upper() if company_name else ""
        company_entry_description = str(company_entry_description).upper() if company_entry_description else "CHILD SUPP"

        # Format company_id to 10 digits (pad or truncate)
        company_id_clean = ''.join(filter(str.isdigit, str(company_id)))[:10]
        company_id_formatted = self._pad_number(company_id_clean, 10, '0')

        record = "5"  # Position 1: Record Type Code
        # Position 2-4: Service Class Code (200, 220, 225, etc.)
        # Format to 3 digits, default to "200" if not provided or invalid
        service_class_code_str = str(service_class_code).strip()[:3] if service_class_code else "200"
        service_class_code_formatted = self._pad_number(service_class_code_str, 3, '0')
        record += service_class_code_formatted
        record += self._pad_string(company_name, 16, 'left', ' ')  # Position 5-20: Company Name
        record += self._pad_string("", 20, 'left', ' ')  # Position 21-40: Blank
        record += company_id_formatted  # Position 41-50: Company Identification (10 digits)
        record += self._pad_string(standard_entry_class, 3, 'left', ' ')  # Position 51-53: SEC Code
        record += self._pad_string(company_entry_description, 10, 'left', ' ')  # Position 54-63: Company Entry Description
        record += self._format_date(pay_date)  # Position 64-69: Company Descriptive Date
        record += self._format_date(pay_date)  # Position 70-75: Effective Entry Date
        record += "   "  # Position 76-78: Blank
        record += "1"  # Position 79: Originator Status Code
        record += self._pad_number(originating_dfi_id[:8], 8, '0')  # Position 80-87: Trace Record Part 1 (8 digits)
        record += self._pad_number(batch_number, 7)  # Position 88-94: Trace Record Part 2 (7 digits)
        
        # Ensure record is exactly 94 characters (excluding newline)
        if len(record) != 94:
            record = record[:94].ljust(94, ' ')
        
        record += "\n"  # Newline
        return record

    def _generate_entry_detail(self, transaction_code, routing_number, account_number, 
                              amount, individual_id, individual_name, trace_number_part1, trace_number_part2,
                              discretionary_data="", addenda_indicator="1"):
        """
        Generate Entry Detail Record (Type 6) per CSV specification.
        Position 1: Record Type Code (6)
        Position 2-3: Transaction Code (22 = checking credit)
        Position 4-11: Receiving DFI ID (8 digits)
        Position 12: Check Digit (1 digit)
        Position 13-29: DFI Account Number (17 chars)
        Position 30-39: Amount (10 digits, in cents)
        Position 40-54: Individual ID Number (15 chars)
        Position 55-76: Individual Name (22 chars)
        Position 77-78: Discretionary Data (2 chars)
        Position 79: Addenda Indicator (1)
        Position 80-87: Trace Record Part 1 (8 digits)
        Position 88-94: Trace Record Part 2 (7 digits)
        """
        # Clean and format routing number (9 digits, use first 8 for DFI ID)
        routing_clean = ''.join(filter(str.isdigit, str(routing_number)))[:9]
        routing_8 = self._pad_number(routing_clean[:8], 8, '0')
        # Check digit is the 9th digit of routing number
        check_digit = routing_clean[8] if len(routing_clean) == 9 else self._calculate_check_digit(routing_8)

        # Clean and format account number (up to 17 chars)
        account_clean = ''.join(filter(str.isalnum, str(account_number)))[:17]
        account_clean = self._pad_string(account_clean, 17, 'left', ' ')

        # Format individual name (up to 22 chars) - convert to uppercase
        name_clean = str(individual_name).upper()[:22] if individual_name else ''
        name_clean = self._pad_string(name_clean, 22, 'left', ' ')

        # Format individual id (up to 15 chars)
        id_clean = str(individual_id)[:15] if individual_id else ''
        id_clean = self._pad_string(id_clean, 15, 'left', ' ')

        record = "6"  # Position 1: Record Type Code
        record += self._pad_number(transaction_code, 2)  # Position 2-3: Transaction Code (22 = checking credit)
        record += routing_8  # Position 4-11: Receiving DFI ID (8 digits)
        record += str(check_digit)  # Position 12: Check Digit (1 digit)
        record += account_clean  # Position 13-29: DFI Account Number (17 chars)
        record += self._format_amount(amount)  # Position 30-39: Amount (10 digits, in cents)
        record += id_clean  # Position 40-54: Individual ID Number (15 chars)
        record += name_clean  # Position 55-76: Individual Name (22 chars)
        record += self._pad_string(discretionary_data, 2, 'left', ' ')  # Position 77-78: Discretionary Data (2 chars)
        record += addenda_indicator  # Position 79: Addenda Indicator (1 = addenda follows for CCD+)
        record += self._pad_number(trace_number_part1, 8)  # Position 80-87: Trace Record Part 1 (8 digits)
        record += self._pad_number(trace_number_part2, 7)  # Position 88-94: Trace Record Part 2 (7 digits)
        
        # Ensure record is exactly 94 characters (excluding newline)
        if len(record) != 94:
            record = record[:94].ljust(94, ' ')
        
        record += "\n"  # Newline
        return record

    def _generate_addenda_record(self, addenda_type_code, segment_identifier, application_identifier,
                                 case_identifier, pay_date, payment_amount, absent_parent_ssn,
                                 medical_support_indicator, absent_parent_name, fips_code,
                                 employment_termination_indicator, addenda_sequence_number, 
                                 entry_detail_sequence_number):
        """
        Generate Addenda Record (Type 7) for CCD+ format per NACHA specification.
        
        Record Structure (94 characters total, excluding newline):
        - Position 1: Record Type Code (7) - Always "7"
        - Position 2-3: Addenda Type Code (05 for CCD+) - Always "05"
        - Position 4-83: Payment Related Information (80 chars) - structured data with delimiters
        - Position 84-87: Addenda Sequence Number (4 digits)
        - Position 88-94: Entry Detail Sequence Number (7 digits)
        
        Payment Related Information structure (positions 4-83, 80 chars total):
        - Position 4-6: Segment Identifier (3 chars)
          * "DED" for child support
          * "TXP" for FTB (Franchise Tax Board)
        - Position 7: Segment Delimiter (*)
        - Position 8-9: Application Identifier (2 chars)
          * "CS" for child support
          * "52", "53", "55", "56", "61", "62" for FTB (depending on type of order)
        - Position 10: Segment Delimiter (*)
        - Position 11-30: Case Identifier (20 chars, left-justified, space-padded)
          * State-assigned case number
        - Position 31: Segment Delimiter (*)
        - Position 32-37: Pay Date (6 chars, YYMMDD format)
          * Employee's Payroll Date
        - Position 38: Segment Delimiter (*)
        - Position 39-48: Payment Amount (10 digits, in cents, zero-padded)
          * Withholding amount that needs to be sent to the agency
        - Position 49: Segment Delimiter (*)
        - Position 50-58: Absent Parent SSN (9 digits, zero-padded)
          * Employee's Social Security Number
        - Position 59: Segment Delimiter (*)
        - Position 60: Medical Support Indicator (1 char, Y or N, uppercase)
          * "Y" or "N" - indicates if medical support is included
        - Position 61: Segment Delimiter (*)
        - Position 62-71: Absent Parent Name (10 chars, format: Last,First, uppercase, space-padded)
          * Employee's Name, format: Last, First
        - Position 72: Segment Delimiter (*)
        - Position 73-79: FIPS Code (7 chars, left-justified, space-padded)
          * State FIPS code identifying the SDU jurisdiction
          * Present in the order details
        - Position 80: Segment Delimiter (*)
        - Position 81-82: Employment Termination Indicator (2 chars)
          * Position 81: Indicator (Y or N, uppercase)
          * Position 82: Space
          * "Y" or "N" - indicates if employee is terminated or not
        - Position 83: Segment Terminator (\)
          * As per document should be backslash, but as per sample files there is a forward slash
        - Position 84-87: Addenda Sequence Number (4 digits)
          * Sequence number (always starts at 0001 for first addenda per entry)
        - Position 88-94: Entry Detail Sequence Number (7 digits)
          * Last 7 digits of associated Entry Detail's trace number
        
        Note: Filler is 0 chars (no filler needed as positions align correctly)
        
        Args:
            addenda_type_code: Addenda type code (5 for CCD+, will be formatted as "05")
            segment_identifier: Segment identifier (DED for child support, TXP for FTB)
            application_identifier: Application identifier (CS for child support, 52/53/55/56/61/62 for FTB)
            case_identifier: Case/Order identifier (max 20 chars, state-assigned case number)
            pay_date: Pay date in YYMMDD format (6 chars, Employee's Payroll Date)
            payment_amount: Payment amount (Decimal, withholding amount in cents)
            absent_parent_ssn: Absent parent SSN (9 digits, Employee's Social Security Number)
            medical_support_indicator: Medical support indicator (Y or N)
            absent_parent_name: Absent parent name (format: Last,First, max 10 chars, Employee's Name)
            fips_code: FIPS code (7 chars total including padding, State FIPS code for SDU jurisdiction)
            employment_termination_indicator: Employment termination indicator (Y or N)
            addenda_sequence_number: Addenda sequence number (4 digits, starts at 0001)
            entry_detail_sequence_number: Entry detail sequence number (7 digits, last 7 digits of trace number)
        
        Returns:
            str: Formatted addenda record (94 characters + newline)
        """
        # Convert all text fields to uppercase as per NACHA specification
        segment_identifier = str(segment_identifier).upper() if segment_identifier else ""
        application_identifier = str(application_identifier).upper() if application_identifier else ""
        case_identifier = str(case_identifier).upper() if case_identifier else ""
        absent_parent_name = str(absent_parent_name).upper() if absent_parent_name else ""
        medical_support_indicator = str(medical_support_indicator).upper() if medical_support_indicator else ""
        employment_termination_indicator = str(employment_termination_indicator).upper() if employment_termination_indicator else ""
        
        # Build structured payment information section (80 characters total, positions 4-83)
        payment_info = ""
        
        # Position 4-6: Segment Identifier (3 chars)
        # "DED" for child support, "TXP" for FTB
        payment_info += self._pad_string(segment_identifier, 3, 'left', ' ')
        payment_info += "*"  # Position 7: Segment Delimiter
        
        # Position 8-9: Application Identifier (2 chars)
        # "CS" for child support, "52"/"53"/"55"/"56"/"61"/"62" for FTB
        payment_info += self._pad_string(application_identifier, 2, 'left', ' ')
        payment_info += "*"  # Position 10: Segment Delimiter
        
        # Position 11-30: Case Identifier (20 chars, left-justified, space-padded)
        # State-assigned case number
        payment_info += self._pad_string(case_identifier, 20, 'left', ' ')
        payment_info += "*"  # Position 31: Segment Delimiter
        
        # Position 32-37: Pay Date (6 chars, YYMMDD format)
        # Employee's Payroll Date
        payment_info += self._pad_string(pay_date, 6, 'left', ' ')
        payment_info += "*"  # Position 38: Segment Delimiter
        
        # Position 39-48: Payment Amount (10 digits, in cents, zero-padded)
        # Withholding amount that needs to be sent to the agency
        payment_info += self._format_amount(payment_amount)
        payment_info += "*"  # Position 49: Segment Delimiter
        
        # Position 50-58: Absent Parent SSN (9 digits, zero-padded)
        # Employee's Social Security Number
        payment_info += self._pad_string(absent_parent_ssn, 9, 'left', '0')
        payment_info += "*"  # Position 59: Segment Delimiter
        
        # Position 60: Medical Support Indicator (1 char, Y or N, uppercase)
        # "Y" or "N" - indicates if medical support is included
        payment_info += self._pad_string(medical_support_indicator, 1, 'left', ' ')
        payment_info += "*"  # Position 61: Segment Delimiter
        
        # Position 62-71: Absent Parent Name (10 chars, format: Last,First, uppercase, space-padded)
        # Employee's Name, format: Last, First
        payment_info += self._pad_string(absent_parent_name, 10, 'left', ' ')
        payment_info += "*"  # Position 72: Segment Delimiter
        
        # Position 73-79: FIPS Code (7 chars, left-justified, space-padded)
        # State FIPS code identifying the SDU jurisdiction, present in the order details
        payment_info += self._pad_string(fips_code, 7, 'left', ' ')
        payment_info += "*"  # Position 80: Segment Delimiter
        
        # Position 81-82: Employment Termination Indicator (2 chars)
        # Position 81: Indicator (Y or N, uppercase)
        # Position 82: Space
        # "Y" or "N" - indicates if employee is terminated or not
        employment_term = (employment_termination_indicator[:1] if employment_termination_indicator else "N") + " "
        payment_info += employment_term
        
        # Position 83: Segment Terminator (1 char)
        # As per document should be backslash, but as per sample files there is a forward slash
        payment_info += "\\"
        
        # Ensure payment_info is exactly 80 characters (positions 4-83)
        # Note: No filler needed (0 chars) as positions align correctly
        payment_info = payment_info[:80]
        payment_info = self._pad_string(payment_info, 80, 'left', ' ')
        
        # Build complete addenda record (94 characters total)
        record = "7"  # Position 1: Record Type Code
        record += self._pad_number(addenda_type_code, 2)  # Position 2-3: Addenda Type Code (05 for CCD+)
        record += payment_info  # Position 4-83: Payment Related Information (80 chars)
        record += self._pad_number(addenda_sequence_number, 4)  # Position 84-87: Addenda Sequence Number (4 digits)
        
        # Entry Detail Sequence Number (position 88-94, 7 digits)
        # Use last 7 digits of trace number part 2
        entry_seq = str(entry_detail_sequence_number)[-7:] if entry_detail_sequence_number else "0000000"
        record += self._pad_number(entry_seq, 7)
        
        # Ensure record is exactly 94 characters (excluding newline)
        if len(record) != 94:
            record = record[:94].ljust(94, ' ')
        
        record += "\n"  # Add newline character
        return record

    def _calculate_check_digit(self, routing_number):
        """Calculate MOD 10 check digit for routing number."""
        if len(routing_number) != 8:
            return '0'
        weights = [3, 7, 1, 3, 7, 1, 3, 7]
        total = sum(int(routing_number[i]) * weights[i] for i in range(8))
        check_digit = (10 - (total % 10)) % 10
        return str(check_digit)

    def _generate_batch_control(self, batch_number, entry_count, addenda_count, entry_hash, 
                                total_debit_amount, total_credit_amount, 
                                company_id, message_auth_code="", 
                                originating_dfi_id="", service_class_code="200"):
        """
        Generate Batch Control Record (Type 8) per CSV specification.
        Position 1: Record Type Code (8)
        Position 2-4: Service Class Code (200, 220, 225, etc.)
          * Must match the Service Class Code from Batch Header (Type 5)
        Position 5-10: Entry/Addenda Count (6 digits)
        Position 11-20: Entry Hash (10 digits)
        Position 21-32: Total Debit Entry Dollar Amount (12 digits)
        Position 33-44: Total Credit Entry Dollar Amount (12 digits)
        Position 45-54: Company Identification (10 digits)
        Position 55-73: Message Authentication Code (19 chars, blank)
        Position 74-79: Reserved (6 chars, blank)
        Position 80-87: Originating DFI Identification (8 digits)
        Position 88-94: Batch Number (7 digits)
        
        Args:
            batch_number: Batch number (7 digits)
            entry_count: Number of entry detail records
            addenda_count: Number of addenda records
            entry_hash: Entry hash (sum of first 8 digits of routing numbers)
            total_debit_amount: Total debit entry dollar amount (Decimal)
            total_credit_amount: Total credit entry dollar amount (Decimal)
            company_id: Company identification (10 digits)
            message_auth_code: Message authentication code (19 chars, optional)
            originating_dfi_id: Originating DFI identification (8 digits)
            service_class_code: Service Class Code (default: "200", must match Batch Header)
        
        Returns:
            str: Formatted batch control record (94 characters + newline)
        """
        # Format company_id to 10 digits (pad or truncate)
        company_id_clean = ''.join(filter(str.isdigit, str(company_id)))[:10]
        company_id_formatted = self._pad_number(company_id_clean, 10, '0')
        
        # Format originating_dfi_id to 8 digits
        originating_dfi_clean = ''.join(filter(str.isdigit, str(originating_dfi_id)))[:8]
        originating_dfi_formatted = self._pad_number(originating_dfi_clean, 8, '0')
        
        record = "8"  # Position 1: Record Type Code
        # Position 2-4: Service Class Code (must match Batch Header)
        # Format to 3 digits, default to "200" if not provided or invalid
        service_class_code_str = str(service_class_code).strip()[:3] if service_class_code else "200"
        service_class_code_formatted = self._pad_number(service_class_code_str, 3, '0')
        record += service_class_code_formatted
        record += self._pad_number(entry_count + addenda_count, 6)  # Position 5-10: Entry/Addenda Count (6 digits)
        record += self._pad_number(entry_hash % 10000000000, 10)  # Position 11-20: Entry Hash (10 digits)
        record += self._format_amount(total_debit_amount, 12)  # Position 21-32: Total Debit Entry Dollar Amount (12 digits)
        record += self._format_amount(total_credit_amount, 12)  # Position 33-44: Total Credit Entry Dollar Amount (12 digits)
        record += company_id_formatted  # Position 45-54: Company Identification (10 digits)
        record += self._pad_string(message_auth_code, 19, 'right', ' ')  # Position 55-73: Message Authentication Code (19 chars)
        record += self._pad_string("", 6, 'right', ' ')  # Position 74-79: Reserved (6 chars)
        record += originating_dfi_formatted  # Position 80-87: Originating DFI Identification (8 digits)
        record += self._pad_number(batch_number, 7)  # Position 88-94: Batch Number (7 digits)
        
        # Ensure record is exactly 94 characters (excluding newline)
        if len(record) != 94:
            record = record[:94].ljust(94, ' ')
        
        record += "\n"  # Newline
        return record

    def _generate_file_control(self, batch_count, block_count, entry_count, addenda_count, entry_hash,
                               total_debit_amount, total_credit_amount):
        """
        Generate File Control Record (Type 9).
        Entry count includes both entry detail and addenda records.
        """
        record = "9"  # Record Type Code
        record += self._pad_number(batch_count, 6)  # Batch Count (6 digits)
        record += self._pad_number(block_count, 6)  # Block Count (6 digits)
        record += self._pad_number(entry_count + addenda_count, 8)  # Entry/Addenda Count (8 digits)
        record += self._pad_number(entry_hash % 10000000000, 10)  # Entry Hash (10 digits)
        record += self._format_amount(total_debit_amount, 12)  # Total Debit Entry Dollar Amount (12 digits)
        record += self._format_amount(total_credit_amount, 12)  # Total Credit Entry Dollar Amount (12 digits)
        record += self._pad_string("", 39, 'right', ' ')  # Reserved (39 chars)
        
        # Ensure record is exactly 94 characters (excluding newline)
        if len(record) != 94:
            record = record[:94].ljust(94, ' ')
        
        record += "\n"  # Newline
        return record

    def _validate_ach_data(self, orders_data):
        """
        Validate all data before file generation.
        Returns (is_valid, error_messages, failed_records)
        """
        error_messages = []
        failed_records = []
        
        for idx, order_data in enumerate(orders_data):
            errors = []
            
            # Validate routing number
            routing = order_data.get('routing_number', '')
            if not routing or not routing.strip():
                errors.append("Routing number is missing")
            
            # Validate account number
            account = order_data.get('account_number', '')
            if not account or not account.strip():
                errors.append("Account number is missing")
            
            # Validate payment amount
            amount = order_data.get('amount', 0)
            if not amount or Decimal(str(amount)) <= 0:
                errors.append("Payment amount must be greater than zero")
            
            # Validate order/case number
            case_id = order_data.get('case_id', '')
            if not case_id or not case_id.strip():
                errors.append("Order/Case number is missing")
            
            # Validate employee identifier
            employee_id = order_data.get('employee_id', '')
            if not employee_id or not str(employee_id).strip():
                errors.append("Employee identifier is missing")
            
            if errors:
                failed_records.append({
                    'index': idx,
                    'case_id': case_id,
                    'errors': errors
                })
                error_messages.extend([f"Record {idx + 1} (Case ID: {case_id}): {err}" for err in errors])
        
        is_valid = len(failed_records) == 0
        return is_valid, error_messages, failed_records

    def _generate_ach_content(self, orders_data, file_params):
        """
        Generate ACH file content in CCD+ format.
        """
        ach_content = []
        
        # Extract file parameters
        immediate_destination = file_params.get('immediate_destination', '')
        immediate_origin = file_params.get('immediate_origin', '')
        immediate_destination_name = file_params.get('immediate_destination_name', '')
        immediate_origin_name = file_params.get('immediate_origin_name', '')
        company_name = file_params.get('company_name', '')
        company_id = file_params.get('company_id', '')
        originating_dfi_id = file_params.get('originating_dfi_id', '')
        
        # Ensure effective_date is a date object
        effective_date = file_params.get('effective_date', date.today())
        if isinstance(effective_date, str):
            try:
                effective_date = datetime.strptime(effective_date, '%Y-%m-%d').date()
            except ValueError:
                effective_date = date.today()
        elif not isinstance(effective_date, date):
            effective_date = date.today()
        
        file_id_modifier = file_params.get('file_id_modifier', 'A')
        batch_number = file_params.get('batch_number', 1)
        service_class_code = file_params.get('service_class_code', '200')  # Default to "200" if not provided
        standard_entry_class = file_params.get('standard_entry_class', 'CCD') 
        pay_date=file_params.get('pay_date') 
        
        # File Header
        creation_time = datetime.now().time()
        file_header = self._generate_file_header(
            immediate_destination=immediate_destination,
            immediate_origin=immediate_origin,
            file_id_modifier=file_id_modifier,
            creation_date=effective_date,
            creation_time=creation_time,
            immediate_destination_name=immediate_destination_name,
            immediate_origin_name=immediate_origin_name,
            batch_number=batch_number
        )
        ach_content.append(file_header)

        # Batch Header
        batch_header = self._generate_batch_header(
            batch_number=batch_number,
            company_name=company_name,
            company_id=company_id,
            pay_date=pay_date,
            standard_entry_class=standard_entry_class,
            originating_dfi_id=originating_dfi_id,
            service_class_code=service_class_code
        )
        ach_content.append(batch_header)

        # Process entries
        entry_count = 0
        addenda_count = 0
        entry_hash = 0
        total_credit_amount = Decimal('0.00')
        total_debit_amount = Decimal('0.00')
        
        # Trace number: Part 1 is originating DFI ID (8 digits), Part 2 is sequential entry number (7 digits)
        trace_part1 = int(originating_dfi_id[:8]) if originating_dfi_id and len(originating_dfi_id) >= 8 else 98708076
        trace_part2 = 1  # Start from 1 for first entry
        addenda_sequence = 1

        for order_data in orders_data:
            try:
                routing_number = order_data.get('routing_number', '')
                account_number = order_data.get('account_number', '')
                amount = Decimal(str(order_data.get('amount', 0)))
                individual_id = str(order_data.get('case_id', ''))[:15]
                individual_name = order_data.get('individual_name', '')
                case_id = order_data.get('case_id', '')
                employee_id = order_data.get('employee_id', '')
                employee_ssn = order_data.get('employee_ssn', '')
                
                # Transaction code: 22 = checking credit (per CSV), 27 = checking credit (alternative)
                transaction_code = order_data.get('transaction_code', 22)
                
                # Extract addenda fields from order_data - convert to uppercase
                segment_identifier = str(order_data.get('segment_identifier', 'DED')).upper()  # DED for child support, TXP for FTB
                application_identifier = str(order_data.get('application_identifier', 'CS')).upper()  # CS for child support
                case_identifier = str(order_data.get('case_identifier', case_id[:20])).upper()
                pay_date_str = self._format_date(pay_date)  # YYMMDD format (6 chars)
                absent_parent_ssn = order_data.get('absent_parent_ssn', employee_ssn)[:9]
                medical_support_indicator = str(order_data.get('medical_support_indicator', 'N')).upper()
                absent_parent_name = order_data.get('absent_parent_name', individual_name)
                # Format name as "Last,First" if not already formatted (max 10 chars)
                if ',' not in absent_parent_name and ' ' in absent_parent_name:
                    name_parts = absent_parent_name.split()
                    if len(name_parts) >= 2:
                        absent_parent_name = f"{name_parts[-1]},{' '.join(name_parts[:-1])}"
                absent_parent_name = str(absent_parent_name).upper()[:10]  # Convert to uppercase and ensure max 10 chars
                fips_code = order_data.get('fips_code', '')[:7]  # FIPS code is 7 chars total (including padding)
                employment_termination_indicator = str(order_data.get('employment_termination_indicator', 'N')).upper()
                
                # Generate Entry Detail Record
                entry_detail = self._generate_entry_detail(
                    transaction_code=transaction_code,
                    routing_number=routing_number,
                    account_number=account_number,
                    amount=amount,
                    individual_id=individual_id,
                    individual_name=individual_name,
                    trace_number_part1=trace_part1,
                    trace_number_part2=trace_part2,
                    addenda_indicator="1"  # CCD+ requires addenda
                )
                ach_content.append(entry_detail)
                entry_count += 1
                
                # Generate Addenda Record (Type 7) for CCD+
                addenda_record = self._generate_addenda_record(
                    addenda_type_code=5,  # 05 for CCD+
                    segment_identifier=segment_identifier,
                    application_identifier=application_identifier,
                    case_identifier=case_identifier,
                    pay_date=pay_date_str,
                    payment_amount=amount,
                    absent_parent_ssn=absent_parent_ssn,
                    medical_support_indicator=medical_support_indicator,
                    absent_parent_name=absent_parent_name,
                    fips_code=fips_code,
                    employment_termination_indicator=employment_termination_indicator,
                    addenda_sequence_number=addenda_sequence,
                    entry_detail_sequence_number=trace_part2
                )
                ach_content.append(addenda_record)
                addenda_count += 1
                addenda_sequence += 1
                
                # Update counters
                trace_part2 += 1  # Increment trace part 2 for next entry
                total_credit_amount += amount
                
                # Add routing number to hash (first 8 digits)
                routing_clean = ''.join(filter(str.isdigit, str(routing_number)))[:8]
                if routing_clean:
                    entry_hash += int(routing_clean[:8])
                    
            except Exception as e:
                logger.error(f"Error processing order data: {str(e)}")
                continue

        # Batch Control
        batch_control = self._generate_batch_control(
            batch_number=batch_number,
            entry_count=entry_count,
            addenda_count=addenda_count,
            entry_hash=entry_hash,
            total_debit_amount=total_debit_amount,
            total_credit_amount=total_credit_amount,
            company_id=company_id,
            originating_dfi_id=originating_dfi_id,
            service_class_code=service_class_code  # Must match Batch Header
        )
        ach_content.append(batch_control)

        # Calculate block count (each block is 10 records)
        total_records = len(ach_content) + 1  # +1 for file control
        block_count = (total_records + 9) // 10  # Round up to nearest 10

        # Pad to complete blocks (each block is 10 records of 94 chars)
        while len(ach_content) < (block_count * 10) - 1:  # -1 for file control
            ach_content.append(" " * 94 + "\n")

        # File Control
        file_control = self._generate_file_control(
            batch_count=1,
            block_count=block_count,
            entry_count=entry_count,
            addenda_count=addenda_count,
            entry_hash=entry_hash,
            total_debit_amount=total_debit_amount,
            total_credit_amount=total_credit_amount
        )
        ach_content.append(file_control)

        return ''.join(ach_content), {
            'entry_count': entry_count,
            'addenda_count': addenda_count,
            'total_credit_amount': total_credit_amount,
            'total_debit_amount': total_debit_amount,
            'block_count': block_count
        }

    # Files are returned directly in HTTP response, not stored in blob storage
    # The store_file parameter only controls whether metadata is saved to database

    def _convert_to_pdf(self, ach_content):
        """Convert ACH content to PDF format."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import inch
            
            buffer = BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            
            # Use Courier (monospace) font for fixed-width formatting
            c.setFont("Courier", 8)
            
            # Set margins
            margin = 0.5 * inch
            x = margin
            y = height - margin
            line_height = 10
            
            # Split content into lines
            lines = ach_content.split('\n')
            
            # Add title
            c.setFont("Helvetica-Bold", 12)
            c.drawString(x, y, "ACH File Content")
            y -= line_height * 2
            c.setFont("Courier", 8)
            
            # Draw each line
            for line in lines:
                if y < margin + line_height:
                    # New page
                    c.showPage()
                    c.setFont("Courier", 8)
                    y = height - margin
                
                # Handle encoding - ensure line is valid string
                try:
                    if isinstance(line, bytes):
                        line = line.decode('utf-8', errors='replace')
                    # Remove or replace any problematic characters
                    line_text = line.encode('ascii', errors='replace').decode('ascii')
                    # Truncate if too long to fit on page
                    max_chars = int((width - 2 * margin) / 4.5)  # Approximate chars per line
                    line_text = line_text[:max_chars] if len(line_text) > max_chars else line_text
                    c.drawString(x, y, line_text)
                except Exception as line_error:
                    logger.warning(f"Error drawing line in PDF: {str(line_error)}")
                    # Skip problematic lines
                    continue
                
                y -= line_height
            
            # Finalize and save the PDF - this is critical
            # c.save() finalizes the PDF and writes it to the buffer
            c.save()
            
            # Get PDF bytes from buffer - must read after save()
            buffer.seek(0)
            pdf_bytes = buffer.getvalue()
            buffer.close()  # Close the original buffer since we have the bytes
            
            # Validate PDF - check if it starts with PDF header
            if not pdf_bytes or len(pdf_bytes) < 4:
                logger.error(f"Generated PDF is invalid - empty or too short: {len(pdf_bytes) if pdf_bytes else 0} bytes")
                raise ValueError("Invalid PDF generated - empty or too short")
            
            if pdf_bytes[:4] != b'%PDF':
                logger.error(f"Generated PDF is invalid - does not start with PDF header. First 20 bytes: {pdf_bytes[:20]}")
                raise ValueError("Invalid PDF generated - missing PDF header")
            
            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
            
            # Return bytes - the response handler will create a new BytesIO for FileResponse
            return pdf_bytes
            
        except ImportError as e:
            # If reportlab is not available, return text content as bytes
            logger.warning(f"reportlab not available: {str(e)}, returning text content for PDF")
            return ach_content.encode('utf-8')
        except Exception as e:
            # Log the error and return text content as fallback
            logger.error(f"Error generating PDF: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # Don't return invalid PDF - raise exception instead
            raise

    def _convert_to_xml(self, ach_content, metadata):
        """Convert ACH content to XML format."""
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_lines.append('<ACHFile>')
        xml_lines.append(f'  <Metadata>')
        xml_lines.append(f'    <PayDate>{metadata.get("pay_date", "")}</PayDate>')
        xml_lines.append(f'    <AgencyPayee>{metadata.get("agency_payee", "")}</AgencyPayee>')
        xml_lines.append(f'    <TotalPaymentCount>{metadata.get("entry_count", 0)}</TotalPaymentCount>')
        xml_lines.append(f'    <TotalPaymentAmount>{metadata.get("total_credit_amount", 0)}</TotalPaymentAmount>')
        xml_lines.append(f'    <GeneratedAt>{metadata.get("generated_at", "")}</GeneratedAt>')
        xml_lines.append(f'  </Metadata>')
        xml_lines.append(f'  <Content><![CDATA[{ach_content}]]></Content>')
        xml_lines.append('</ACHFile>')
        return '\n'.join(xml_lines)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['orders_data', 'file_params'],
            properties={
                'orders_data': openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'case_id': openapi.Schema(type=openapi.TYPE_STRING),
                            'routing_number': openapi.Schema(type=openapi.TYPE_STRING),
                            'account_number': openapi.Schema(type=openapi.TYPE_STRING),
                            'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'individual_name': openapi.Schema(type=openapi.TYPE_STRING),
                            'employee_id': openapi.Schema(type=openapi.TYPE_STRING),
                            'transaction_code': openapi.Schema(type=openapi.TYPE_INTEGER, description='Transaction code (22 = checking credit, 27 = alternative)'),
                            'employee_ssn': openapi.Schema(type=openapi.TYPE_STRING, description='Employee SSN (9 digits)'),
                            'segment_identifier': openapi.Schema(type=openapi.TYPE_STRING, description='Segment Identifier (DED for child support, TXP for FTB)'),
                            'application_identifier': openapi.Schema(type=openapi.TYPE_STRING, description='Application Identifier (CS for child support, 52/53/55/56/61/62 for FTB)'),
                            'case_identifier': openapi.Schema(type=openapi.TYPE_STRING, description='Case Identifier (20 chars)'),
                            'absent_parent_ssn': openapi.Schema(type=openapi.TYPE_STRING, description='Absent Parent SSN (9 digits)'),
                            'medical_support_indicator': openapi.Schema(type=openapi.TYPE_STRING, description='Medical Support Indicator (Y or N)'),
                            'absent_parent_name': openapi.Schema(type=openapi.TYPE_STRING, description='Absent Parent Name (format: Last,First, max 20 chars)'),
                            'fips_code': openapi.Schema(type=openapi.TYPE_STRING, description='FIPS Code (6 chars)'),
                            'employment_termination_indicator': openapi.Schema(type=openapi.TYPE_STRING, description='Employment Termination Indicator (Y or N)'),
                        }
                    )
                ),
                'file_params': openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'immediate_destination': openapi.Schema(type=openapi.TYPE_STRING),
                        'immediate_origin': openapi.Schema(type=openapi.TYPE_STRING),
                        'immediate_destination_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'immediate_origin_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'company_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'company_id': openapi.Schema(type=openapi.TYPE_STRING),
                        'originating_dfi_id': openapi.Schema(type=openapi.TYPE_STRING),
                        'effective_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                        'file_id_modifier': openapi.Schema(type=openapi.TYPE_STRING),
                        'batch_number': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'service_class_code': openapi.Schema(
                            type=openapi.TYPE_STRING, 
                            description='Service Class Code (200 = Mixed, 220 = Credits only, 225 = Debits only). Default: 200'
                        ),
                        'standard_entry_class': openapi.Schema(
                            type=openapi.TYPE_STRING, 
                            description='Standard Entry Class Code (e.g., CCD, PPD, CTX, etc.). Default: CCD'
                        ),
                    }
                ),
                'export_format': openapi.Schema(type=openapi.TYPE_STRING, enum=['txt', 'pdf', 'xml']),
                'pay_date': openapi.Schema(type=openapi.TYPE_STRING, format='date'),
                'agency_payee': openapi.Schema(type=openapi.TYPE_STRING),
                'store_file': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Store metadata in database (file returned in response, not stored in blob)'),
            }
        ),
        responses={
            200: 'ACH file generated successfully',
            400: 'Invalid parameters or validation failed',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        """
        Generate ACH file in CCD+ format from provided data.
        
        """
        try:
            data = request.data
            orders_data = data.get('orders_data', [])
            file_params = data.get('file_params', {})
            export_format = data.get('export_format', 'txt').lower()
            pay_date_str = data.get('pay_date')
            agency_payee = data.get('agency_payee', '')
            store_file = data.get('store_file', False)  # Default to False - return file directly
            
            if not orders_data:
                return ResponseHelper.error_response(
                    "orders_data is required",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate data
            is_valid, error_messages, failed_records = self._validate_ach_data(orders_data)
            if not is_valid:
                return ResponseHelper.error_response(
                    "Validation failed",
                    error={
                        'errors': error_messages,
                        'failed_records': failed_records
                    },
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Parse pay_date
            if pay_date_str:
                try:
                    pay_date = datetime.strptime(pay_date_str, '%Y-%m-%d').date()
                except ValueError:
                    pay_date = date.today()
            else:
                pay_date = file_params.get('pay_date', date.today())
                if isinstance(pay_date, str):
                    pay_date = datetime.strptime(pay_date, '%Y-%m-%d').date()
            
            # Generate ACH content
            ach_content, file_stats = self._generate_ach_content(orders_data, file_params)
            
            # Convert to requested format
            if export_format == 'pdf':
                try:
                    file_content = self._convert_to_pdf(ach_content)
                    content_type = 'application/pdf'
                    file_extension = 'pdf'
                except Exception as pdf_error:
                    logger.error(f"PDF generation failed: {str(pdf_error)}")
                    return ResponseHelper.error_response(
                        "Failed to generate PDF file",
                        error=str(pdf_error),
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            elif export_format == 'xml':
                file_content = self._convert_to_xml(ach_content, {
                    'pay_date': pay_date_str or str(pay_date),
                    'agency_payee': agency_payee,
                    'entry_count': file_stats['entry_count'],
                    'total_credit_amount': float(file_stats['total_credit_amount']),
                    'generated_at': datetime.now().isoformat()
                })
                content_type = 'application/xml'
                file_extension = 'xml'
            else:  # txt
                file_content = ach_content.encode('utf-8')
                content_type = 'text/plain'
                file_extension = 'txt'
            
            # Generate filename
            file_id_modifier = file_params.get('file_id_modifier', 'A')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f"ACH_{pay_date.strftime('%Y%m%d')}_{file_id_modifier}_{timestamp}.{file_extension}"
            
            # Calculate file size
            file_size = len(file_content) if isinstance(file_content, bytes) else len(file_content.encode('utf-8'))
            
            # Save metadata to database if requested (without storing file in blob)
            if store_file:
                try:
                    case_ids = [order.get('case_id') for order in orders_data]
                    trace_base = int(file_params.get('originating_dfi_id', '1000000')[:8]) * 100000 if file_params.get('originating_dfi_id') else 1000000
                    transaction_refs = [f"Trace: {trace_base + i}" for i in range(len(orders_data))]
                    
                    ach_file_record = ACHFile.objects.create(
                        file_name=file_name,
                        file_format=export_format,
                        file_url=None,  # Not storing in blob, file returned in response
                        file_size=file_size,
                        generated_by=request.user if request.user.is_authenticated else None,
                        pay_date=pay_date,
                        agency_payee=agency_payee,
                        total_payment_count=file_stats['entry_count'],
                        total_payment_amount=file_stats['total_credit_amount'],
                        batch_id=str(file_params.get('batch_number', 1)),
                        file_id_modifier=file_id_modifier,
                        associated_case_ids=json.dumps(case_ids),
                        transaction_references=json.dumps(transaction_refs)
                    )
                    logger.info(f"ACH file metadata saved: {ach_file_record.id}")
                except Exception as e:
                    logger.error(f"Failed to save ACH file metadata: {str(e)}")
            
            # Prepare response with file content
            # For PDF, use FileResponse which handles binary content better
            if export_format == 'pdf':
                # Ensure file_content is bytes
                if not isinstance(file_content, bytes):
                    file_content = file_content.encode('utf-8') if isinstance(file_content, str) else bytes(file_content)
                
                # Create a BytesIO object for FileResponse
                pdf_buffer = BytesIO(file_content)
                response = FileResponse(
                    pdf_buffer,
                    content_type='application/pdf',
                    as_attachment=True,
                    filename=file_name
                )
                response['Content-Length'] = str(file_size)
            else:
                response = HttpResponse(file_content, content_type=content_type)
                response['Content-Disposition'] = f'attachment; filename="{file_name}"'
                response['Content-Length'] = str(file_size)
            
            return response
            
        except Exception as e:
            logger.exception("Error generating ACH file")
            return ResponseHelper.error_response(
                "Failed to generate ACH file",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ACHFileListView(APIView):
    """
    API view to retrieve list of generated ACH files.
    """
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('pay_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('batch_id', openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter('format', openapi.IN_QUERY, type=openapi.TYPE_STRING, enum=['txt', 'pdf', 'xml']),
        ],
        responses={200: 'List of ACH files retrieved successfully'}
    )
    def get(self, request):
        """Retrieve list of generated ACH files with optional filters."""
        try:
            queryset = ACHFile.objects.filter(is_active=True).order_by('-generated_at')
            
            pay_date = request.query_params.get('pay_date')
            if pay_date:
                queryset = queryset.filter(pay_date=pay_date)
            
            batch_id = request.query_params.get('batch_id')
            if batch_id:
                queryset = queryset.filter(batch_id=batch_id)
            
            file_format = request.query_params.get('format')
            if file_format:
                queryset = queryset.filter(file_format=file_format)
            
            files_data = []
            for ach_file in queryset:
                files_data.append({
                    'id': ach_file.id,
                    'file_name': ach_file.file_name,
                    'file_format': ach_file.file_format,
                    'file_url': ach_file.file_url,
                    'file_size': ach_file.file_size,
                    'generated_at': ach_file.generated_at.isoformat(),
                    'generated_by': ach_file.generated_by.username if ach_file.generated_by else None,
                    'pay_date': ach_file.pay_date.isoformat(),
                    'agency_payee': ach_file.agency_payee,
                    'total_payment_count': ach_file.total_payment_count,
                    'total_payment_amount': float(ach_file.total_payment_amount),
                    'batch_id': ach_file.batch_id,
                    'associated_case_ids': json.loads(ach_file.associated_case_ids) if ach_file.associated_case_ids else [],
                    'transaction_references': json.loads(ach_file.transaction_references) if ach_file.transaction_references else []
                })
            
            return ResponseHelper.success_response(
                "ACH files retrieved successfully",
                data=files_data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.exception("Error retrieving ACH files")
            return ResponseHelper.error_response(
                "Failed to retrieve ACH files",
                error=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


logger = logging.getLogger(__name__)


class AchGarnishmentConfigListCreateAPIView(APIView):

    def get(self, request):
        try:
            configs = AchGarnishmentConfig.objects.all().order_by("-created_at")
            serializer = AchGarnishmentConfigSerializer(configs, many=True)

            return ResponseHelper.success_response(
                message="Fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Error fetching ACH configs")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            serializer = AchGarnishmentConfigSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Created successfully",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )

            return ResponseHelper.error_response(
                message="Validation Failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception("Error creating ACH config")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

from django.shortcuts import get_object_or_404


class AchGarnishmentConfigDetailAPIView(APIView):

    def get_object(self, pk):
        return get_object_or_404(AchGarnishmentConfig, pk=pk)

    def get(self, request, pk):
        try:
            config = self.get_object(pk)
            serializer = AchGarnishmentConfigSerializer(config)

            return ResponseHelper.success_response(
                message="Fetched successfully",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Error fetching ACH config details")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, pk):
        try:
            config = self.get_object(pk)
            serializer = AchGarnishmentConfigSerializer(config, data=request.data)

            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )

            return ResponseHelper.error_response(
                message="Validation Failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception("Error updating ACH config")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, pk):
        try:
            config = self.get_object(pk)
            serializer = AchGarnishmentConfigSerializer(config, data=request.data, partial=True)

            if serializer.is_valid():
                serializer.save()
                return ResponseHelper.success_response(
                    message="Updated successfully",
                    data=serializer.data,
                    status_code=status.HTTP_200_OK
                )

            return ResponseHelper.error_response(
                message="Validation Failed",
                error=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.exception("Error partially updating ACH config")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, pk):
        try:
            config = self.get_object(pk)
            config.delete()

            return ResponseHelper.success_response(
                message="Deleted successfully",
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception("Error deleting ACH config")
            return ResponseHelper.error_response(
                message=str(e),
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
