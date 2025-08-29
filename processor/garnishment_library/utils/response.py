from rest_framework.response import Response
from rest_framework import status

class ResponseHelper:

    @staticmethod
    def success_response(message, data=None, status_code=status.HTTP_200_OK):
        response_data = {
            'success': True,
            'message': message,
            'status_code': status_code,
            'data': data if data else {}
        }
        return Response(response_data, status=status_code)

    @staticmethod
    def error_response(message, error=None, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR):
        response_data = {
            'success': False,
            'message': message,
            'status_code': status_code,
            'error': error if error else ''
        }
        return Response(response_data, status=status_code)



class UtilityClass:

    @staticmethod
    def build_response(withholding_amt, disposable_earning, basis, cap):
        return {
            "withholding_amt": withholding_amt,
            "disposable_earning": disposable_earning,
            "withholding_basis": basis,
            "withholding_cap": cap,
        }


class CalculationResponse:
    DE_AMOUNT_LESS_THAN_THRESHOLD = "DE amount is less than the FMW lower threshold, the withholding amount is $0"

    DE_AMOUNT_GREATER_THAN_THRESHOLD = "DE amount is greater than the FMW upper threshold, the withholding amount is $0"
    DE_AMOUNT_WITHIN_THRESHOLD = "DE amount is within the FMW thresholds, the withholding amount is calculated based on the FMW and the DE amount"

    @staticmethod
    def get_zero_withholding_response(message1, message2):
        return f"{message1} amount is less than the {message2}, the withholding amount is $0"

