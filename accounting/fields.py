from django.db.models import DecimalField

class CurrencyField(DecimalField):    
    def __init__(self, *args, **kw):
        kw['max_digits'] = 10
        kw['decimal_places'] = 4
        super(CurrencyField, self).__init__(*args, **kw)

