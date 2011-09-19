from django.contrib import admin

from accounting.models import Account, Transaction, Invoice

admin.site.register(Account)
admin.site.register(Transaction)
admin.site.register(Invoice)  
