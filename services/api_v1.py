from services.lib.flask_restplus import Api
from flask import Blueprint
from .endpoints_v1.datasets import ns as datasets_ns
from .endpoints_v1.projects import ns as projects_ns
from .endpoints_v1.persons import ns as persons_ns
from .endpoints_v1.awards import ns as awards_ns


blueprint = Blueprint('api', __name__, url_prefix='/api/v1.0')
api = Api(blueprint, version='v1.0', title='USAP-DC API', ordered=True, doc='/doc',
          description='A Rest API service for accessing data from USAP-DC')

api.add_namespace(awards_ns)
api.add_namespace(datasets_ns)
api.add_namespace(persons_ns)
api.add_namespace(projects_ns)
