import json
from six.moves.urllib.parse import urlencode
from unittest import TestCase

import flask
from flask import Response
from flask_restful import Resource, Api
from nose_parameterized import parameterized

from flask_request_validator import CompositeRule
from flask_request_validator import (
    Enum,
    GET,
    Param,
    Pattern,
    validate_params
)
from flask_request_validator.exceptions import InvalidRequest
from flask_request_validator.rules import MaxLength, MinLength
from flask_request_validator.validator import PATH, FORM, JSON

app = flask.Flask(__name__)
test_api = Api(app, '/v1')

app.testing = True


@test_api.resource('/resource')
class TestApi(Resource):

    @validate_params(
        Param('key', JSON, int),
        Param('sure', JSON, bool)
    )
    def put(self, key, sure):
        return Response(
            json.dumps([
                [key, key.__class__.__name__],
                [sure, sure.__class__.__name__],
            ]),
            mimetype='application/json'
        )

    @validate_params(
        Param('cities', GET, list),
        Param('countries', GET, dict)
    )
    def get(self, cities, countries):
        return Response(
            json.dumps({
                'cities': [cities, cities.__class__.__name__],
                'countries': [countries, countries.__class__.__name__],
            }),
            mimetype='application/json'
        )

type_composite = CompositeRule(Enum('type1', 'type2'))


@app.route('/main/<string:key>/<string:uuid>', methods=['POST'])
@validate_params(
    Param('key', PATH, str, rules=[Enum('key1', 'key2')]),
    Param('uuid', PATH, str, rules=[Pattern(r'^[a-z-_.]{8,10}$')]),
    Param('sure', GET, bool, False),
    Param('sys', FORM, str, rules=[Pattern(r'^[a-z.]{3,6}$')]),
    Param('types', FORM, str, rules=type_composite),
    Param('price', FORM, float, False),
    Param('cities', FORM, list, False),
    Param('dql', FORM, dict, False),
    Param('default', FORM, dict, False, default=lambda: ['test']),
)
def route_form(key, uuid, sure, sys, types, price, cities, dql, default):
    return json.dumps([
        [key, key.__class__.__name__],
        [uuid, uuid.__class__.__name__],
        [sure, sure.__class__.__name__],
        [sys, sys.__class__.__name__],
        [types, types.__class__.__name__],
        [price, price.__class__.__name__],
        [cities, cities.__class__.__name__],
        [dql, dql.__class__.__name__],
        [default, default.__class__.__name__],
    ])


@app.route('/json/<int:id>', methods=['POST'])
@validate_params(
    Param('id', PATH, int),
    Param('first_name', JSON, str, rules=[MaxLength(6)]),
    Param('last_name', JSON, str, rules=[MinLength(2)]),
    Param('age', JSON, int),
    Param('names', JSON, list),
    Param('height', JSON, int, False, default=174),
    Param('children', JSON, int, False),
)
def route_json(id_, first_name, last_name, age, names, height, children):
    return json.dumps([
        [id_, id_.__class__.__name__],
        [first_name, first_name.__class__.__name__],
        [last_name, last_name.__class__.__name__],
        [age, age.__class__.__name__],
        [names, names.__class__.__name__],
        [height, height.__class__.__name__],
        [children, children.__class__.__name__],
    ])


@app.route('/invalid', methods=['POST'])
@validate_params(
    Param('first_name', JSON, str, rules=[MaxLength(6)]),
    Param('last_name', JSON, str, rules=[MinLength(6)]),
    Param('street', JSON, str),
    Param('city', JSON, str, rules=[Enum('Minsk')]),
    Param('uuid', JSON, str, rules=[Pattern(r'^[a-z-_.]{8,10}$')]),
    Param('types', JSON, str, rules=type_composite),
)
def invalid_route(first_name, last_name, street, city, uuid):
    pass


class TestValidator(TestCase):

    def test_invalid_route(self):
        with app.test_client() as client:
            try:
                client.post(
                    '/invalid',
                    data=json.dumps(dict(
                        first_name='very-very-long',
                        last_name='small',
                        city='wrong',
                        uuid='!#wrong#!',
                        types='wrong'
                    )),
                    content_type='application/json'
                )
            except InvalidRequest as e:
                self.assertDictEqual(
                    e.errors,
                    {
                        'city': ['Incorrect value "wrong". Allowed values: (\'Minsk\',)'],
                        'first_name': ['Invalid length for value "very-very-long". Max length = 6'],
                        'last_name': ['Invalid length for value "small". Min length = 6'],
                        'uuid': ['Value "!#wrong#!" does not match pattern ^[a-z-_.]{8,10}$'],
                        'street': ['Value is required'],
                        'types': ['Incorrect value "wrong". Allowed values: (\'type1\', \'type2\')']
                    }
                )

    def test_valid_form(self):
        with app.test_client() as client:
            sys = 'key.a'
            types = 'type1'
            price = 2.99
            key = 'key1'
            uuid = 'test_test'
            sure = True
            cities = 'Minsk, Prague, Berlin'
            dql = 'orderBy: DESC, select: name'
            data = client.post(
                '/main/%s/%s?sure=%s' % (key, uuid, str(sure)),
                data=dict(
                    sys=sys,
                    types=types,
                    price=price,
                    cities=cities,
                    dql=dql
                )
            )

            cities = cities.split(', ')

            self.assertEqual(
                json.loads(data.get_data(as_text=True)),
                [
                    [key, key.__class__.__name__],
                    [uuid, uuid.__class__.__name__],
                    [sure, sure.__class__.__name__],
                    [sys, sys.__class__.__name__],
                    [types, types.__class__.__name__],
                    [price, price.__class__.__name__],
                    [cities, cities.__class__.__name__],
                    [{'orderBy': 'DESC', 'select': 'name'}, 'dict'],
                    [['test'], 'list'],
                ]
            )

    def test_valid_json(self):
        with app.test_client() as client:
            first_name = 'Ridley'
            last_name = 'Scott'
            age = 79
            names = ['Aliens', 'Prometheus']
            data = client.post(
                '/json/1',
                data=json.dumps(dict(
                    first_name=first_name,
                    last_name=last_name,
                    age=age,
                    names=names
                )),
                content_type='application/json'
            )

            self.assertEqual(
                json.loads(data.get_data(as_text=True)),
                [
                    [1, 'int'],
                    [first_name, first_name.__class__.__name__],
                    [last_name, last_name.__class__.__name__],
                    [age, age.__class__.__name__],
                    [names, names.__class__.__name__],
                    [174, 'int'],
                    [None, None.__class__.__name__],
                ]
            )


class TestParam(TestCase):
    def test_types(self):
        param_int = Param('test', FORM, int)
        param_list = Param('test', FORM, list)
        param_dict = Param('test', FORM, dict)
        param_bool = Param('test', FORM, bool)
        param_none = Param('test', FORM)

        self.assertEqual(1, param_int.value_to_type('1'))
        self.assertEqual(True, param_bool.value_to_type('1'))
        self.assertEqual(True, param_bool.value_to_type('true'))
        self.assertEqual(True, param_bool.value_to_type('True'))
        self.assertEqual(False, param_bool.value_to_type('0'))
        self.assertEqual(False, param_bool.value_to_type('false'))
        self.assertEqual(False, param_bool.value_to_type('False'))

        self.assertEqual(
            ['Minsk', 'Prague', 'Berlin'],
            param_list.value_to_type('Minsk, Prague, Berlin')
        )

        self.assertEqual(
            {
                'country': 'Belarus',
                'capital': 'Minsk'
            },
            param_dict.value_to_type('country: Belarus, capital: Minsk')
        )

        data = {'test': {'test': ['test1', 'test2']}}
        self.assertEqual(data, param_none.value_to_type(data))


class TestRestfull(TestCase):

    @parameterized.expand([
        ({'sure': str(True)}, ),
        ({'key': 1}, ),
    ])
    def test_put_raises(self, data):
        with app.test_client() as client:
            with self.assertRaises(InvalidRequest):
                client.put(
                    '/v1/resource',
                    data=json.dumps(data),
                    content_type='application/json'
                )

    def test_put_ok(self):
        key = 1
        sure = True

        with app.test_client() as client:
            data = client.put(
                '/v1/resource',
                data=json.dumps(dict(sure=sure, key=key)),
                content_type='application/json'
            )
            self.assertEqual(
                json.loads(data.get_data(as_text=True), encoding='utf-8'),
                [
                    [key, key.__class__.__name__],
                    [sure, sure.__class__.__name__],
                ]
            )

    def test_get_ok(self):
        cities = ['Minsk', 'Tbilisi', ]
        countries = {'belarus': 'minsk', 'georgia': 'tbilisi'}
        with app.test_client() as client:
            data = client.get(
                '/v1/resource?' + urlencode({
                    'cities': ','.join(cities),
                    'countries': 'belarus:minsk,georgia:tbilisi'
                }),
            )

            self.assertDictEqual(
                json.loads(data.get_data(as_text=True)),
                {
                    'cities': [cities, cities.__class__.__name__],
                    'countries': [countries, countries.__class__.__name__],
                }
            )
