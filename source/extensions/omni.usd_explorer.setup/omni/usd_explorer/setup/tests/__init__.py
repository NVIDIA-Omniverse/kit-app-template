# run startup tests first
from .test_app_startup import *
# run all other tests after
from .test_extensions import *
from .test_release_config import *
from .test import *
from .test_state_manager import *
