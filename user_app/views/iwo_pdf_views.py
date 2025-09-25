
from rest_framework import status
from vercel_blob import put
import numpy as np
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from rest_framework.parsers import MultiPartParser, FormParser
import os
from user_app.serializers import (IWOPDFFilesSerializer, WithholdingOrderDataSerializers)
import logging
import time
import random
import traceback as t
import string
import json
from rest_framework.response import Response
from rest_framework.views import APIView
import pandas as pd
from user_app.models import (IWODetailsPDF, IWOPDFFiles)
from user_app.models.iwo_pdf.iwo_pdf_extraction import WithholdingOrderData
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from user_app.constants import (
    EmployeeFields as EE,
    GarnishmentTypeFields as GT,
    CalculationFields as CA,
    PayrollTaxesFields as PT,
    CalculationResponseFields as CR,
    ResponseMessages,
    BatchDetail
)

logger = logging.getLogger(__name__)


class InsertIWODetailView(APIView):
    """
    API view to insert IWO (Income Withholding Order) detail records.
    Handles POST requests with robust validation and exception handling.
    """

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                #'cid': openapi.Schema(type=openapi.TYPE_STRING, description='Case ID'),
                EE.EMPLOYEE_ID: openapi.Schema(type=openapi.TYPE_STRING, description='Employee ID'),
                'IWO_Status': openapi.Schema(type=openapi.TYPE_STRING, description='IWO Status'),
            },
            required=['cid', EE.EMPLOYEE_ID, 'IWO_Status']
        ),
        responses={
            201: 'IWO detail inserted successfully',
            400: 'Missing required fields or invalid data',
            500: 'Internal server error'
        }
    )
    def post(self, request):
        try:
            # Parse JSON body
            if isinstance(request.data, dict):
                data = request.data
            else:
                try:
                    data = json.loads(request.body)
                except Exception:
                    return Response(
                        {
                            'error': ResponseMessages.INVALID_GARNISHMENT_DATA,
                            'status_code': status.HTTP_400_BAD_REQUEST
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            cid = data.get('cid')
            ee_id = data.get(EE.EMPLOYEE_ID)
            IWO_Status = data.get('IWO_Status')

            # Validate required fields
            missing_fields = [field for field in [
                'cid', EE.EMPLOYEE_ID, 'IWO_Status'] if data.get(field) is None]
            if missing_fields:
                return Response(
                    {
                        'error': f"Missing required fields: {', '.join(missing_fields)}",
                        'status_code': status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create and save the IWO_Details_PDF instance
            iwo_detail = IWODetailsPDF(
                cid=cid,
                ee_id=ee_id,
                IWO_Status=IWO_Status
            )
            iwo_detail.save()

            return Response(
                {
                    'message': 'IWO detail inserted successfully',
                    'status_code': status.HTTP_201_CREATED
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            # logger.error(f"Error inserting IWO detail: {e}")
            return Response(
                {
                    'error': f"Internal server error: {str(e)}",
                    'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Helper function to replace NaNs with None recursively


def clean_data_for_json(data):
    """
    Recursively convert NaN to None and NumPy types to native Python types
    so the structure is JSON serializable.
    """
    if isinstance(data, dict):
        return {k: clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_json(item) for item in data]
    elif pd.isna(data):
        return None
    elif isinstance(data, (np.integer, np.floating)):
        return data.item()
    elif isinstance(data, (np.bool_, bool)):
        return bool(data)
    else:
        return data

class ConvertExcelToJsonView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='file',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="Excel file to upload"
            ),
            openapi.Parameter(
                name='title',
                in_=openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False,
                description="Optional title"
            )
        ],
        responses={
            200: 'File uploaded and processed successfully',
            400: 'No file provided or missing key in data',
            422: 'Data value error',
            500: 'Internal server error'
        }
    )

    # def post(self, request,*args,**kwargs):
    #     file = request.FILES.get('file')

    #     if not file:
    #         return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

    #     try:
    #         # Load Excel sheets
    #         garnishment_df = pd.read_excel(
    #             file, sheet_name='Garnishment Order')
    #         garnishment_df.columns = garnishment_df.columns.str.strip().str.lower()

    #         payroll_df = pd.read_excel(
    #             file, sheet_name='Payroll Batch', header=[0, 1])
    #         payroll_df.columns = payroll_df.columns.map(
    #             lambda x: '_'.join(str(i)
    #                                for i in x) if isinstance(x, tuple) else x
    #         ).str.lower().str.strip()
    #         # garnishment_df[GT.FTB_TYPE] = garnishemnr
            


    #         # Define column mapping dictionaries
    #         payroll_column_map = {
    #             'unnamed: 1_level_0_eeid': EE.EMPLOYEE_ID,
    #             'unnamed: 0_level_0_caseid': EE.CASE_ID,
    #             'unnamed: 2_level_0_payperiod': EE.PAY_PERIOD,
    #             'unnamed: 3_level_0_payrolldate': EE.PAYROLL_DATE,
    #             'earnings_grosspay': CA.GROSS_PAY,
    #             'earnings_wages': CA.WAGES,
    #             'earnings_commission&bonus': CA.COMMISSION_AND_BONUS,
    #             'earnings_nonaccountableallowances': CA.NON_ACCOUNTABLE_ALLOWANCES,
    #             'taxes_fedtaxamt': PT.FEDERAL_INCOME_TAX,
    #             'taxes_statetaxamt': PT.STATE_TAX,
    #             'taxes_local/othertaxes': PT.LOCAL_TAX,
    #             'taxes_medtax': PT.MEDICARE_TAX,
    #             'taxes_oasditax': PT.SOCIAL_SECURITY_TAX,
    #             'deductions_medicalinsurance': PT.MEDICAL_INSURANCE_PRETAX,
    #             'deductions_sdi': PT.CALIFORNIA_SDI,
    #             'deductions_lifeinsurance': PT.LIFE_INSURANCE,
    #             'taxes_wilmingtontax': PT.WILMINGTON_TAX,
    #             'deductions_uniondues': PT.UNION_DUES,
    #             'deductions_netpay': CA.NET_PAY,
    #             'deductions_famlitax': PT.FAMLI_TAX,
    #             'deductions_industrialinsurance': PT.INDUSTRIAL_INSURANCE,
    #         }

    #         garnishment_column_map = {
    #             'eeid': EE.EMPLOYEE_ID, 'caseid': EE.CASE_ID, 'ssn': EE.SSN,'ismultiplegarnishment': EE.IS_MULTIPLE_GARNISHMENT,
    #             'supportsecondfamily': EE.SUPPORT_SECOND_FAMILY, 'supports2ndfam': EE.SUPPORT_SECOND_FAMILY,
    #             'orderedamount': CA.ORDERED_AMOUNT, 'ordered$': CA.ORDERED_AMOUNT,
    #             'arrear>12weeks': EE.ARREARS_GREATER_THAN_12_WEEKS,
    #             'arrears_greater_than_12_weeks': EE.ARREARS_GREATER_THAN_12_WEEKS,
    #             'workstate': EE.WORK_STATE,  'homestate': EE.HOME_STATE,
    #             'no.ofexemptionsincludingself': EE.NO_OF_EXEMPTION_INCLUDING_SELF, 'no.ofexemptionincludingself': EE.NO_OF_EXEMPTION_INCLUDING_SELF,
    #             'garntype': EE.GARNISHMENT_TYPE, 'ftbtype' : GT.FTB_TYPE,
    #             'arrearamount': CA.ARREAR_AMOUNT, 'arrear$': CA.ARREAR_AMOUNT,
    #             'no. ofdependentchild(underthe ageof16)': EE.NO_OF_DEPENDENT_CHILD,
    #             'isblind': EE.IS_BLIND, 'age': EE.AGE, 'spouseage': EE.SPOUSE_AGE,
    #             'filingstatus': EE.FILING_STATUS, 'isspouseblind': EE.IS_SPOUSE_BLIND,
    #             'statementofexemptionreceiveddate': EE.STATEMENT_OF_EXEMPTION_RECEIVED_DATE,
    #             'no.ofstudentdefaultloan': EE.NO_OF_STUDENT_DEFAULT_LOAN,
    #             # 'debt type': EE.DEBT_TYPE,
    #             'garnstartdate': EE.GARN_START_DATE,
    #             'consumerdebt': EE.CONSUMER_DEBT, 'non-consumerdebt': EE.NON_CONSUMER_DEBT}
                
            

    #         # Drop empty columns and rename
    #         garnishment_df.dropna(axis=1, how='all', inplace=True)
    #         payroll_df.dropna(axis=1, how='all', inplace=True)

    #         garnishment_df.rename(columns=garnishment_column_map, inplace=True)
    #         payroll_df.rename(columns=payroll_column_map, inplace=True)

    #         if 'ismultiplegarnishment' not in garnishment_df.columns:
    #             garnishment_df['ismultiplegarnishment'] = False
    #         else:
    #             garnishment_df["is_multiple_garnishment_type"] = garnishment_df["is_multiple_garnishment_type"].fillna(0).astype(int).astype(bool)

    #         # # Strip 'case_id' fields before merging
    #         garnishment_df[EE.CASE_ID] = garnishment_df[EE.CASE_ID].str.strip()
    #         payroll_df[EE.CASE_ID] = payroll_df[EE.CASE_ID].str.strip()
    #         garnishment_df[EE.EMPLOYEE_ID] = garnishment_df[EE.EMPLOYEE_ID].str.strip()
    #         payroll_df[EE.EMPLOYEE_ID] = payroll_df[EE.EMPLOYEE_ID].str.strip()
    #         garnishment_df[EE.GARNISHMENT_TYPE] = garnishment_df[EE.GARNISHMENT_TYPE].str.strip()

    #         # Formated "mm-dd-yyyy"
    #         date_cols = [
    #             'statement_of_exemption_received_date', 'garn_start_date']
    #         garnishment_df[date_cols] = garnishment_df[date_cols].apply(
    #             lambda col: col.dt.strftime('%m-%d-%Y'))
            
    #         # Merge on both employee ID and case ID
    #         merged_df = pd.merge(
    #             payroll_df,
    #             garnishment_df,
    #             on=[EE.EMPLOYEE_ID, EE.CASE_ID],
    #             how='inner',  
    #             suffixes=('', '_garnishment')
    #         )

    #         # Clean specific columns
    #         if EE.FILING_STATUS in merged_df.columns and merged_df[EE.FILING_STATUS].notna().any():
    #             merged_df[EE.FILING_STATUS] = merged_df[EE.FILING_STATUS].str.strip().str.lower(
    #             ).str.replace(" ", "_")
    #         else:
    #             merged_df[EE.FILING_STATUS] = None

    #         merged_df[EE.ARREARS_GREATER_THAN_12_WEEKS] = merged_df[EE.ARREARS_GREATER_THAN_12_WEEKS].astype(bool).apply(
    #             lambda x: True if str(x).lower() in ['true', '1',1,True,"Yes"] else False
    #         )

    #         merged_df[EE.SUPPORT_SECOND_FAMILY] = merged_df[EE.SUPPORT_SECOND_FAMILY].astype(bool).apply(
    #             lambda x: True if str(x).lower() in ['true', '1',1,True,"Yes"] else False
    #         )

    #         merged_df[EE.GARNISHMENT_TYPE] = merged_df[EE.GARNISHMENT_TYPE].str.strip().str.replace(' ', '_')
            
    #         if GT.FTB_TYPE in merged_df.columns:
    #              merged_df[GT.FTB_TYPE] = (merged_df[GT.FTB_TYPE].fillna('').astype(str).str.strip().str.lower().str.replace(' ', '_').replace('', None))
    #         else:
    #             merged_df[GT.FTB_TYPE] = None


    #         # Generate dynamic batch ID
    #         batch_id = f"B{int(time.time() % 1000):03d}{random.choice(string.ascii_uppercase)}"

    #         # Build JSON structure
    #         output_json = {BatchDetail.BATCH_ID: batch_id, "cases": []}

    #         for ee_id, group in merged_df.groupby(f"{EE.EMPLOYEE_ID}"):
    #             first_row = group.iloc[0]

    #             is_multiple = str(first_row.get(EE.IS_MULTIPLE_GARNISHMENT, "")).strip().lower() in ["true", "1"]

    #             if is_multiple:
    #                 garnishment_data = []
    #                 for garn_type, sub_group in group.groupby(EE.GARNISHMENT_TYPE):
    #                     garn_type = garn_type.lower()
    #                     type_data = {
    #                         EE.GARNISHMENT_TYPE: garn_type,
    #                         "data": []
    #                     }

    #                     for _, row in sub_group.iterrows():
    #                         entry = {
    #                             EE.CASE_ID: row.get(EE.CASE_ID),
    #                             CA.ORDERED_AMOUNT: row.get(CA.ORDERED_AMOUNT),
    #                             CA.ARREAR_AMOUNT: row.get(CA.ARREAR_AMOUNT)
    #                         }
                                
    #                         type_data["data"].append(entry)

    #                     garnishment_data.append(type_data)

    #                 garnishment_orders = [item[EE.GARNISHMENT_TYPE].lower() for item in garnishment_data]

    #             else:
    #                 garn_type = first_row.get(EE.GARNISHMENT_TYPE).lower()
    #                 garnishment_data = [{
    #                     EE.GARNISHMENT_TYPE: garn_type,
    #                     "data": [
    #                         {
    #                             EE.CASE_ID: row.get(EE.CASE_ID),
    #                             CA.ORDERED_AMOUNT: row.get(CA.ORDERED_AMOUNT),
    #                             CA.ARREAR_AMOUNT: row.get(CA.ARREAR_AMOUNT)
    #                         }
    #                         for _, row in group.iterrows()
    #                     ]
    #                 }]

    #                 garnishment_orders = [garn_type]


    #             # Append employee data to output JSON
    #             output_json["cases"].append({
    #                 EE.EMPLOYEE_ID: ee_id,
    #                 EE.WORK_STATE: first_row.get(EE.WORK_STATE, "").strip(),
    #                 EE.HOME_STATE: first_row.get(EE.HOME_STATE, "").strip(),
    #                 EE.NO_OF_EXEMPTION_INCLUDING_SELF: first_row.get(EE.NO_OF_EXEMPTION_INCLUDING_SELF),
    #                 EE.IS_MULTIPLE_GARNISHMENT: first_row.get(EE.IS_MULTIPLE_GARNISHMENT),
    #                 EE.NO_OF_STUDENT_DEFAULT_LOAN: first_row.get(EE.NO_OF_STUDENT_DEFAULT_LOAN),
    #                 EE.PAY_PERIOD: first_row.get(EE.PAY_PERIOD),
    #                 EE.FILING_STATUS: first_row.get(EE.FILING_STATUS),
    #                 CA.WAGES: first_row.get(CA.WAGES, 0),
    #                 CA.COMMISSION_AND_BONUS: first_row.get(CA.COMMISSION_AND_BONUS, 0),
    #                 CA.NON_ACCOUNTABLE_ALLOWANCES: first_row.get(CA.NON_ACCOUNTABLE_ALLOWANCES, 0),
    #                 CA.GROSS_PAY: first_row.get(CA.GROSS_PAY, 0),
    #                 PT.PAYROLL_TAXES: {
    #                     PT.FEDERAL_INCOME_TAX: first_row.get(PT.FEDERAL_INCOME_TAX, 0),
    #                     PT.SOCIAL_SECURITY_TAX: first_row.get(PT.SOCIAL_SECURITY_TAX, 0),
    #                     PT.MEDICARE_TAX: first_row.get(PT.MEDICARE_TAX, 0),
    #                     PT.STATE_TAX: first_row.get(PT.STATE_TAX, 0),
    #                     PT.LOCAL_TAX: first_row.get(PT.LOCAL_TAX, 0),
    #                     PT.UNION_DUES: first_row.get(PT.UNION_DUES, 0),
    #                     PT.WILMINGTON_TAX: first_row.get(PT.WILMINGTON_TAX, 0),
    #                     PT.MEDICAL_INSURANCE_PRETAX: first_row.get(PT.MEDICAL_INSURANCE_PRETAX, 0),
    #                     PT.INDUSTRIAL_INSURANCE: first_row.get(PT.INDUSTRIAL_INSURANCE, 0),
    #                     PT.LIFE_INSURANCE: first_row.get(PT.LIFE_INSURANCE, 0),
    #                     PT.CALIFORNIA_SDI: first_row.get(PT.CALIFORNIA_SDI, 0),
    #                     PT.FAMLI_TAX: first_row.get(PT.FAMLI_TAX, 0)
    #                 },
    #                 CA.NET_PAY: first_row.get(CA.NET_PAY),
    #                 EE.IS_BLIND: first_row.get(EE.IS_BLIND),
    #                 EE.STATEMENT_OF_EXEMPTION_RECEIVED_DATE: first_row.get(EE.STATEMENT_OF_EXEMPTION_RECEIVED_DATE),
    #                 EE.GARN_START_DATE: first_row.get(EE.GARN_START_DATE),
    #                 EE.NON_CONSUMER_DEBT: first_row.get(EE.NON_CONSUMER_DEBT),
    #                 EE.CONSUMER_DEBT: first_row.get(EE.CONSUMER_DEBT),
    #                 EE.AGE: first_row.get(EE.AGE),
    #                 EE.SPOUSE_AGE: first_row.get(EE.SPOUSE_AGE),
    #                 EE.IS_SPOUSE_BLIND: first_row.get(EE.IS_SPOUSE_BLIND),
    #                 EE.SUPPORT_SECOND_FAMILY: first_row.get(EE.SUPPORT_SECOND_FAMILY),
    #                 EE.NO_OF_DEPENDENT_CHILD: first_row.get(EE.NO_OF_DEPENDENT_CHILD, 0),
    #                 EE.ARREARS_GREATER_THAN_12_WEEKS: first_row.get(EE.ARREARS_GREATER_THAN_12_WEEKS),
    #                 GT.FTB_TYPE : first_row.get(GT.FTB_TYPE, "None"),
    #                 EE.GARNISHMENT_DATA: garnishment_data,
    #                 EE.GARNISHMENT_ORDERS: garnishment_orders
    #             })
    #         output_json = clean_data_for_json(output_json)
    #         return Response(output_json, status=status.HTTP_200_OK)
    #     except KeyError as e:
    #         return Response({"error": f"Missing key in data: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
    #     except ValueError as e:
    #         return Response({"error": f"Data value error: {str(e)}"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    #     except Exception as e:
    #         return Response({"error": f"Internal server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def post(self, request,*args,**kwargs):
        file = request.FILES.get('file')

        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payroll_df = pd.read_excel(
                file, sheet_name='Payroll Batch', header=[0, 1])
            payroll_df.columns = payroll_df.columns.map(
                lambda x: '_'.join(str(i)
                                   for i in x) if isinstance(x, tuple) else x
            ).str.lower().str.strip()
            # garnishment_df[GT.FTB_TYPE] = garnishemnt
            
            # Define column mapping dictionaries
            payroll_column_map={
                'unnamed: 0_level_0_client id':EE.CLIENT_ID,
                'unnamed: 1_level_0_eeid': EE.EMPLOYEE_ID,
                'unnamed: 2_level_0_payperiod': EE.PAY_PERIOD,
                'unnamed: 3_level_0_payrolldate': EE.PAYROLL_DATE,
                'earnings_wages': CA.WAGES,
                'earnings_commission&bonus': CA.COMMISSION_AND_BONUS,
                'earnings_nonaccountableallowances': CA.NON_ACCOUNTABLE_ALLOWANCES,
                'earnings_grosspay': CA.GROSS_PAY,
                'taxes_fedtaxamt': PT.FEDERAL_INCOME_TAX,
                'taxes_statetaxamt': PT.STATE_TAX, 
                'taxes_local/othertaxes': PT.LOCAL_TAX,
                'taxes_medtax': PT.MEDICARE_TAX, 
                'taxes_oasditax': PT.SOCIAL_SECURITY_TAX,
                'taxes_wilmingtontax': PT.WILMINGTON_TAX,
                'deductions_sdi': PT.CALIFORNIA_SDI,
                'deductions_medicalinsurance': PT.MEDICAL_INSURANCE_PRETAX,
                'deductions_lifeinsurance': PT.LIFE_INSURANCE,
                'deductions_401k':PT.RETIREMENT_401K,
                'deductions_industrialinsurance': PT.INDUSTRIAL_INSURANCE,
                'deductions_uniondues': PT.UNION_DUES,
                'deductions_netpay': CA.NET_PAY,


            }
            # Drop empty columns and rename
            payroll_df.dropna(axis=1, how='all', inplace=True)
            payroll_df.rename(columns=payroll_column_map, inplace=True)

           
            # Strip 
            payroll_df[EE.EMPLOYEE_ID] = payroll_df[EE.EMPLOYEE_ID].str.strip()


            # Generate dynamic batch ID
            batch_id = f"B{int(time.time() % 1000):03d}{random.choice(string.ascii_uppercase)}"

            # Build JSON structure
            output_json = {BatchDetail.BATCH_ID: batch_id, "cases": []}

            # Loop over each row in the DataFrame
            for _, row in payroll_df.iterrows():
                client_id = row.get(EE.CLIENT_ID)
                ee_id = row.get(EE.EMPLOYEE_ID)
                
                output_json["cases"].append({
                    EE.CLIENT_ID: client_id,
                    EE.EMPLOYEE_ID: ee_id,
                    EE.PAY_PERIOD: row.get(EE.PAY_PERIOD),
                    EE.PAYROLL_DATE: row.get(EE.PAYROLL_DATE),
                    CA.WAGES: row.get(CA.WAGES, 0),
                    CA.COMMISSION_AND_BONUS: row.get(CA.COMMISSION_AND_BONUS, 0),
                    CA.NON_ACCOUNTABLE_ALLOWANCES: row.get(CA.NON_ACCOUNTABLE_ALLOWANCES, 0),
                    CA.GROSS_PAY: row.get(CA.GROSS_PAY, 0),
                    PT.PAYROLL_TAXES: {
                        PT.FEDERAL_INCOME_TAX: row.get(PT.FEDERAL_INCOME_TAX, 0),
                        PT.STATE_TAX: row.get(PT.STATE_TAX, 0),
                        PT.LOCAL_TAX: row.get(PT.LOCAL_TAX, 0),
                        PT.MEDICARE_TAX: row.get(PT.MEDICARE_TAX, 0),
                        PT.SOCIAL_SECURITY_TAX: row.get(PT.SOCIAL_SECURITY_TAX, 0),
                        PT.WILMINGTON_TAX: row.get(PT.WILMINGTON_TAX, 0),
                        PT.CALIFORNIA_SDI: row.get(PT.CALIFORNIA_SDI, 0),
                        PT.MEDICAL_INSURANCE_PRETAX: row.get(PT.MEDICAL_INSURANCE_PRETAX, 0),
                        PT.LIFE_INSURANCE: row.get(PT.LIFE_INSURANCE, 0),
                        PT.RETIREMENT_401K: row.get(PT.RETIREMENT_401K, 0),
                        PT.INDUSTRIAL_INSURANCE: row.get(PT.INDUSTRIAL_INSURANCE, 0),
                        PT.UNION_DUES: row.get(PT.UNION_DUES, 0),
                    },
                    CA.NET_PAY: row.get(CA.NET_PAY, 0),
                })

            output_json = clean_data_for_json(output_json)
            return Response(output_json, status=status.HTTP_200_OK)
        except KeyError as e:
            return Response({"error": f"Missing key in data: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": f"Data value error: {str(e)}"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as e:
            return Response({"error": f"Internal server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



def handle_single_file(file):
    """
    Handles the upload, storage, and analysis of a single PDF file.
    Returns serialized data or error details.
    """
    try:
        file_bytes = file.read()
        endpoint = os.getenv("AZURE_ENDPOINT")
        key = os.getenv("AZURE_KEY")

        if not endpoint or not key:
            raise ValueError("Azure endpoint or key not configured.")

        # Upload file to blob storage
        blob_info = put(f"PDFFiles/{file.name}", file_bytes)
        blob_url = blob_info.get("url")
        if not blob_url:
            raise ValueError("Failed to upload file to blob storage.")

        # Save file record in database
        obj = IWOPDFFiles.objects.create(name=file.name, pdf_url=blob_url)
        serializer = IWOPDFFilesSerializer(obj)

        # Analyze file content using Azure Form Recognizer
        document_analysis_client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
        poller = document_analysis_client.begin_analyze_document(
            model_id="from_data", document=file_bytes)
        result = poller.result()

        documents_data = []
        for idx, doc in enumerate(result.documents):
            fields = {
                field_name: (field.value if field.value else 0)
                for field_name, field in doc.fields.items()
            }
            fields["id"] = obj.id
            documents_data.append({"fields": fields})

        # Save extracted data to withholding_order_data model
        if documents_data:
            WithholdingOrderData.objects.create(
                **documents_data[0]["fields"])

        return serializer.data

    except Exception as e:
        # Log the error if logging is set up
        # logger.error(f"Error in handle_single_file: {e}")
        return {
            'success': False,
            'message': 'Error occurred while uploading the file',
            'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
            'data': None,
            "error": str(e)
        }
file_upload_schema = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        'file': openapi.Schema(
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(type=openapi.TYPE_STRING,
                                format=openapi.FORMAT_BINARY),
            description="Upload one or more PDF files"
        ),
    },
    required=['file']
)


class PDFUploadView(APIView):
    """
    API view to handle uploading and processing of multiple PDF files.
    """

    @swagger_auto_schema(
        operation_description="Upload one or more PDF files",
        request_body=file_upload_schema,
        responses={
            201: openapi.Response(description="PDF files uploaded successfully"),
            400: openapi.Response(description="No files provided"),
            500: openapi.Response(description="Internal server error"),
        }
    )
    def post(self, request):
        try:
            files = request.FILES.getlist("file")
            if not files:
                return Response({"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST)

            results = []
            for file in files:
                result = handle_single_file(file)
                results.append(result)

            return Response({
                'success': True,
                "message": "IWO PDF Files Successfully uploaded",
                "status_code": status.HTTP_201_CREATED,
                "results": results
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Error occurred while uploading the file',
                'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GETIWOPDFData(APIView):
    """
    API view to retrieve withholding order data for given IDs.
    Provides robust exception handling and clear response messages.
    """

    def get(self, request, *args, **kwargs):
        try:
            # Get 'ids' parameter from query string
            ids_param = request.query_params.get('ids')
            if not ids_param:
                return Response({
                    'success': False,
                    'message': 'No IDs provided in query parameters.',
                    'status_code': status.HTTP_400_BAD_REQUEST
                }, status=status.HTTP_400_BAD_REQUEST)

            # Split and clean IDs
            ids = [id_.strip()
                   for id_ in ids_param.split(',') if id_.strip().isdigit()]
            if not ids:
                return Response({
                    'success': False,
                    'message': 'No valid IDs provided.',
                    'status_code': status.HTTP_400_BAD_REQUEST
                }, status=status.HTTP_400_BAD_REQUEST)

            # Query the database for matching records
            files = WithholdingOrderData.objects.filter(id__in=ids)
            if not files.exists():
                return Response({
                    'success': False,
                    'message': 'No data found for the provided IDs.',
                    'status_code': status.HTTP_404_NOT_FOUND
                }, status=status.HTTP_404_NOT_FOUND)

            serializer = WithholdingOrderDataSerializers(files, many=True)
            response_data = {
                'success': True,
                'message': 'Data retrieved successfully',
                'status_code': status.HTTP_200_OK,
                'data': serializer.data
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            # logger.error(f"Error retrieving IWO PDF data: {e}")
            response_data = {
                'success': False,
                'message': 'Failed to retrieve data',
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                'error': str(e)
            }
            return Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
