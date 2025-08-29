from rest_framework import serializers
from processor.models.federal_tax_levy import (
    FedFilingStatus, AddExemptions,StdExemptions
)   

class FedFilingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = FedFilingStatus
        fields = '__all__'


class StdExemptionSerializer(serializers.ModelSerializer):
    year = serializers.CharField(source='year.year', read_only=True)
    filing_status = serializers.CharField(source='fs.name', read_only=True)
    payperiod = serializers.CharField(source='pp.name', read_only=True)
    
    class Meta:
        model = StdExemptions
        fields = ['std_id', 'num_exemptions', 'exempt_amt', 'year', 'filing_status', 'payperiod']

class AddExemptionSerializer(serializers.ModelSerializer):
    year = serializers.CharField(source='year.year', read_only=True)
    filing_status = serializers.CharField(source='fs.name', read_only=True)
    
    class Meta:
        model = AddExemptions
        fields = ['add_id', 'year', 'filing_status', 'num_exemptions', 'daily', 'weekly', 'biweekly', 'semimonthly', 'monthly']

   