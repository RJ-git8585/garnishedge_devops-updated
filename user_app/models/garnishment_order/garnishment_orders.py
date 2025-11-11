from django.db import models

class GarnishmentOrder(models.Model):
    case_id = models.CharField(max_length=255, unique=True)
    employee = models.ForeignKey(
        'user_app.EmployeeDetail', on_delete=models.CASCADE, related_name="garnishments")
    issuing_state = models.ForeignKey(
        'processor.State', on_delete=models.CASCADE, related_name="garnishments")
    
    garnishment_type = models.ForeignKey('processor.GarnishmentType', on_delete=models.CASCADE,db_index=True)
    is_consumer_debt = models.BooleanField(default=False)
    deduction_code = models.CharField(max_length=255)
    issued_date = models.DateField(blank=True, null=True)
    received_date = models.DateField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    stop_date = models.DateField(blank=True, null=True)
    deduction_code = models.CharField(max_length=255)  
    ordered_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pay_period_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pay_date = models.DateField(blank=True, null=True)
    current_child_support = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    current_medical_support = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    current_spousal_support = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    child_support_arrear = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    medical_support_arrear = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    spousal_support_arrear = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)

    override_child_support = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    override_medical_support = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    override_spousal_support = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    override_child_support_arrear = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    override_medical_support_arrear = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    override_spousal_support_arrear = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)

    amount_of_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=0.00,blank=True,null=True)
    
    garnishment_fees = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    fips_code = models.CharField(max_length=255,blank=True, null=True)

    override_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    override_limit = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    override_arrear =models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    override_percent =models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    override_start_date = models.DateField(blank=True, null=True)
    override_stop_date = models.DateField(blank=True, null=True)
    paid_till_date = models.DateField(blank=True, null=True)
    
    arrear_greater_than_12_weeks = models.BooleanField(
        default=False, blank=False)
    arrear_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)

    current_child_support=models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    
    current_medical_support =models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    
    current_spousal_support =models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    
    medical_support_arrear =models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
        
    child_support_arrear =models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    
    spousal_support_arrear =models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    
    total_amount_owed = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    monthly_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    exempt_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    ytd_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    ach_sent = models.BooleanField(default=False)
    ap_check = models.BooleanField(default=False)

    voucher_for_payroll = models.CharField(max_length=255, blank=True, null=True)
    date_of_ap_payment = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['case_id']),
        ]
        db_table = "garnishment_order"
