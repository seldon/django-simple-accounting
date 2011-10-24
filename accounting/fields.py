from django.db.models import DecimalField

class CurrencyField(DecimalField):    
    def __init__(self, *args, **kwargs):
        kwargs['max_digits'] = 10
        kwargs['decimal_places'] = 4
        super(CurrencyField, self).__init__(*args, **kwargs)

