from django.db import models

class Person(models.Model):
    name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)

class Company(models.Model):
    name = models.CharField(max_length=50)
    referrer = models.ForeignKey(Person)
    
