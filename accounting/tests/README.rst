For running tests, issue the command:

{{{

django-admin.py test --settings=accounting.tests.settings tests

}}}

To get more details from the test runner, add the ``-v 2`` flag:

{{{

django-admin.py test --settings=accounting.tests.settings tests -v 2

}}}


Be sure that the ``accounting`` package is on your Python import search path !


