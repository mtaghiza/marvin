#!/usr/bin/env python
# encoding: utf-8

'''
Licensed under a 3-clause BSD license.

Revision History:
    Initial Version: 2016-02-23 14:13:28 by Brian Cherinka
    2016-02-23 - made some test sample forms with wtforms+sqlalchemy - B. Cherinka
    2016-03-02 - generalized the form to build all forms - B. Cherinka
'''

from __future__ import print_function
from __future__ import division
from marvin import marvindb, config
from marvin.core import MarvinError, MarvinUserWarning
from collections import defaultdict
from wtforms import StringField, validators, SelectField, SelectMultipleField, IntegerField, ValidationError, SubmitField
from wtforms.widgets import Select
from wtforms_alchemy import model_form_factory
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.attributes import InstrumentedAttribute
import re
import warnings

# flask_wtf does not work locally - OUTSIDE APPLICATON CONTEXT; need some kind of toggle for web version and not???
if config._inapp:
    from flask_wtf import Form
else:
    from wtforms import Form

__all__ = ['MarvinForm']


def tree():
    return defaultdict(tree)


# Base form class
BaseModelForm = model_form_factory(Form)


class ModelForm(BaseModelForm):
    ''' sub class a new ModelForm so it works with Flask-WTF in APP mode;  for auto CSRF tokens...who knows...'''
    @classmethod
    def get_session(self):
        return marvindb.session

''' Builds a dictionary for modelclasses with key ClassName and value SQLalchemy model class ; '''
modelclasses = marvindb.buildUberClassDict()


# class factory
def formClassFactory(name, model, baseclass):
    ''' Generates a new WTForm class based on SQLalchemy model class.  Each class contains as attributes
        Meta = a class called Meta.  Meta.model contains the SQLalchemy ModelClass
        data = a dictionary of parameters: form input that gets mapped to the sqlalchemy parameter
        errors = a dictionary of errors returned by invalid form validation
        validate = a method to validate all elements in this form
        parameter_X = a WTForm Field mapped to respective sqlalchemy table column

        e.g.
        The ModelClass IFUDesign mapped to mangadatadb.ifu_design sql table gets transformed into
        WTForm IFUDesignForm, with IFUDesignForm.Meta.model = sdss.internal.database.utah.mangadb.DataModelClasses.IFUDesign
    '''

    Meta = type('Meta', (object,), {'model': model})
    newclass = type(name, (baseclass,), {'Meta': Meta})
    return newclass

# build a wtform select field for operators; tested but no longer used ; can't seem to attach operator field to every individual parameter
opdict = {'le': '<=', 'ge': '>=', 'gt': '>', 'lt': '<', 'ne': '!=', 'eq': '='}
ops = [(key, val) for key, val in opdict.items()]
# operator = SelectField(u'Operator', choices=ops)


class ParamFxnLookupDict(dict):
    ''' Parameter function lookup for new function expressions
    '''

    def __getitem__(self, key):

        lowkey = key.lower()
        mykeys = self.keys()

        inkey = lowkey in mykeys
        if not inkey:
            raise KeyError('{0} does not match any column.'.format(lowkey))
        else:
            keycount = mykeys.count(lowkey)
            if keycount > 1:
                raise KeyError('{0} matches multiple parameters in the lookup'
                               ' table'.format(lowkey))
            else:
                return dict.__getitem__(self, lowkey)


class ParamFormLookupDict(dict):

    def __init__(self):
        self._init_table_shortcuts()
        self._init_name_shortcuts()
        self._mplver = config.mplver

    def __getitem__(self, key):
        """Checks if `key` is a unique column name and return the value."""

        # Update shortcuts upon MPL changes
        if self._mplver != config.mplver:
            self._init_table_shortcuts()
            self._init_name_shortcuts()
            self._mplver = config.mplver

        # Applies shortcuts
        keySplits = self._apply_shortcuts(key)

        # Get key matches
        matches = self._get_matches(keySplits)

        # Check DAP Junk keys
        isdapjunk = any(['mangadapdb.junk' in m for m in matches])
        if isdapjunk:
            keySplits = self._apply_shortcuts(matches[0])
            matches = self._get_matches(keySplits)

        # Return matched key
        if len(matches) == 0:
            # No matches. This returns the standards KeyError from dict
            raise KeyError('{0} does not match any column.'.format(key))
        elif len(matches) == 1:
            # One match: returns the form.
            return dict.__getitem__(self, matches[0])
        else:
            # Multiple results. Raises a custom error.
            raise KeyError(
                '{0} matches multiple parameters in the lookup table: {1}'
                .format(key, ', '.join(matches)))

    def mapToColumn(self, keys):
        """Returns the model class column in the WFTForm."""

        if not isinstance(keys, (list, tuple)):
            keys = [keys]

        columns = []
        for key in keys:
            wtfForm = self[key]
            column = key.split('.')[-1]
            columns.append(getattr(wtfForm.Meta.model, column))

        if len(columns) == 1:
            return columns[0]
        else:
            return columns

    def _init_table_shortcuts(self):
        ''' initialize the table shortcuts '''

        self._tableShortcuts = {'ifu': 'ifudesign'}
        self._set_junk_shortcuts()

    def _init_name_shortcuts(self):
        ''' initialize the name shortcuts '''
        self._nameShortcuts = {'haflux': 'emline_gflux_ha_6564'}

    def _apply_shortcuts(self, key):
        ''' Apply the shortcuts to the key '''

        # Gets the paths that match the key
        keySplits = key.split('.')

        # Applies table shortcuts
        if len(keySplits) >= 2 and keySplits[-2] in self._tableShortcuts:
            keySplits[-2] = self._tableShortcuts[keySplits[-2]]

        # Applies name shortcuts
        if len(keySplits) >= 1 and keySplits[-1] in self._nameShortcuts:
            keySplits[-1] = self._nameShortcuts[keySplits[-1]]

        return keySplits

    def _set_junk_shortcuts(self):
        ''' Sets the DAP junk shortcuts based on MPL '''

        newmpls = [m for m in config._mpldict.keys() if m >= 'MPL-4']
        if '4' in config.mplver:
            dapcut = {'junk{0}'.format(m.split('-')[1]): 'junk' for m in newmpls}
        else:
            mdigit = config.mplver.split('-')[1]
            dapcut = {'junk{0}'.format(m.split('-')[1]): 'junk{0}'.format(mdigit) for m in newmpls}
            dapcut.update({'junk': 'junk{0}'.format(mdigit)})
        self._tableShortcuts.update(dapcut)

    def _get_matches(self, keySplits):
        ''' Get the matches from a set of key splits '''
        matches = [path for path in self
                   if all([keySplits[-1 - ii] == path.split('.')[-1 - ii]
                           for ii in range(len(keySplits))])]
        return matches


# Custom validator for MainForm
class ValidOperand(object):
    def __init__(self, opstring='[<>=]', message=None):
        self.opstring = opstring
        if not message:
            message = u'Field must contain at least a valid operand of {0}.'.format(self.opstring)
        self.message = message

    def __call__(self, form, field):
        infield = re.search(self.opstring, field.data)
        if not infield:
            raise ValidationError(self.message)


class SearchForm(Form):
    ''' Main Search Level WTForm for Marvin '''
    searchbox = StringField('Search', [validators.Length(min=3, message='Input must have at least 3 characters'),
                            validators.DataRequired(message='Input filter string required'),
                            ValidOperand('[<>=]', message='Input must contain a valid operand.')])
    parambox = StringField("<a target='_blank' href='https://api.sdss.org/doc/manga/marvin/refactor/query_params.html'>Query Parameters</a>")
    returnparams = SelectMultipleField("<a target='_blank' href='https://api.sdss.org/doc/manga/marvin/refactor/query_params.html'>Return Parameters</a>")
    submit = SubmitField('Submit')


class MarvinForm(object):
    ''' Core Marvin Form object. '''

    def __init__(self, *args, **kwargs):
        ''' Initialize the obect.  On init, generates all the WTForms from the ModelClasses.

        _param_form_lookup = dictionary of all modelclass parameters of form {'SQLalchemy ModelClass parameter name': WTForm Class}
        '''

        self._param_form_lookup = ParamFormLookupDict()
        self._param_fxn_lookup = ParamFxnLookupDict()
        self._paramtree = tree()
        self._generateFormClasses(modelclasses)
        self._generateFxns()
        self.SearchForm = SearchForm
        self._cleanParams()

    def _generateFormClasses(self, classes):
        ''' Loops over all ModelClasses and generates a new WTForm class.  New form classes are named as [ModelClassName]Form.
            Sets the new form as an attribute on MarvinForm.  Also populates the _param_to_form_lookup dictonary with
            all ModelClass/WTForm parameters and their corresponding forms.

            e.g.  _param_form_lookup['name'] = marvin.tools.query.forms.IFUDesignForm
        '''

        for key, val in classes.items():
            classname = '{0}Form'.format(key)
            try:
                newclass = formClassFactory(classname, val, ModelForm)
            except Exception as e:
                warnings.warn('class {0} not Formable'.format(key), MarvinUserWarning)
            else:
                self.__setattr__(classname, newclass)
                self._loadParams(newclass)

    def _loadParams(self, newclass):
        ''' Loads all parameters from wtforms into a dictionary with
            key, value = {'parameter_name': 'parent WTForm name'}.
            Ignores hidden attributes and the Meta class
        '''

        model = newclass.Meta.model
        schema = model.__table__.schema
        tablename = model.__table__.name

        mapper = sa_inspect(model)
        for item in mapper.all_orm_descriptors:
            if type(item) == hybrid_property:
                key = item.__name__
            elif type(item) == InstrumentedAttribute:
                key = item.key
            else:
                continue

            lookupKeyName = schema + '.' + tablename + '.' + key
            self._param_form_lookup[lookupKeyName] = newclass
            self._paramtree[newclass.Meta.model.__name__][key]

    def callInstance(self, form, params=None, **kwargs):
        ''' Creates an instance of a specified WTForm.  '''
        return form(**params) if params else form(**kwargs)

    def _generateFxns(self):
        ''' Generate the fxn dictionary

            TODO: make this general and not hard-coded

            The key is the function name used in the query syntax.
            The value is the method call that lives in Query

        '''
        self._param_fxn_lookup['npergood'] = 'getPercent'

    def _getDapKeys(self):
        ''' Returns the DAP keys from the Junk tables
        '''
        dapkeys = [k for k in self._param_form_lookup.keys() if 'mangadapdb.junk' in k]
        dapkeys.sort()
        return dapkeys

    def _cleanParams(self):
        ''' Clean up the parameter-form lookup dictionary '''

        # remove keys for pk, mangadatadb.sample, test_, and cube_header
        new = ParamFormLookupDict()
        for k, v in self._param_form_lookup.items():
            if 'pk' not in k and \
               'mangadatadb.sample' not in k and \
               'test_' not in k and \
               'cube_header' not in k:
                new[k] = v

        # make new dictionary
        self._param_form_lookup = new


