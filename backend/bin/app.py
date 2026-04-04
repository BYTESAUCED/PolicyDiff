# Owner: AZ
# CDK app entry point — instantiates all 4 stacks in dependency order.
# Configuration is loaded from backend/.env (copy from .env.example and fill in values).

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ directory (one level up from bin/)
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)

import aws_cdk as cdk
import cdk_nag

from lib.storage_stack import PolicyDiffStorageStack
from lib.compute_stack import PolicyDiffComputeStack
from lib.api_stack import PolicyDiffApiStack
from lib.frontend_stack import PolicyDiffFrontendStack

_log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Configuration from .env ───────────────────────────────────────────────────

aws_region = os.environ.get("AWS_REGION", "us-east-1")
cdk_account = os.environ.get("CDK_DEFAULT_ACCOUNT") or os.environ.get("CDK_DEFAULT_ACCOUNT")

auth0_domain = os.environ.get("AUTH0_DOMAIN", "")
auth0_audience = os.environ.get("AUTH0_AUDIENCE", "")
auth0_client_id = os.environ.get("AUTH0_CLIENT_ID", "")

github_oauth_token = os.environ.get("GITHUB_OAUTH_TOKEN", "")
github_owner = os.environ.get("GITHUB_OWNER", "PLACEHOLDER")
github_repo = os.environ.get("GITHUB_REPO", "policydiff")

bedrock_model_arn = os.environ.get(
    "BEDROCK_MODEL_ARN",
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5",
)

# ── Validation warnings ───────────────────────────────────────────────────────

if not auth0_domain:
    _log.warning("AUTH0_DOMAIN not set — JWT authorizer will be disabled. Set it in backend/.env")
if not auth0_audience:
    _log.warning("AUTH0_AUDIENCE not set — JWT authorizer will be disabled. Set it in backend/.env")
if not auth0_client_id:
    _log.warning("AUTH0_CLIENT_ID not set — frontend Auth0 config will be empty. Set it in backend/.env")
if not github_oauth_token:
    _log.warning("GITHUB_OAUTH_TOKEN not set — Amplify GitHub connection will use placeholder. Set it in backend/.env")

# ── CDK App ───────────────────────────────────────────────────────────────────

app = cdk.App()

env = cdk.Environment(
    account=cdk_account or None,
    region=aws_region,
)

storage = PolicyDiffStorageStack(app, "PolicyDiffStorageStack", env=env)

compute = PolicyDiffComputeStack(
    app,
    "PolicyDiffComputeStack",
    storage_stack=storage,
    bedrock_model_arn=bedrock_model_arn,
    env=env,
)
compute.add_dependency(storage)

api = PolicyDiffApiStack(
    app,
    "PolicyDiffApiStack",
    compute_stack=compute,
    auth0_domain=auth0_domain,
    auth0_audience=auth0_audience,
    env=env,
)
api.add_dependency(compute)

frontend = PolicyDiffFrontendStack(
    app,
    "PolicyDiffFrontendStack",
    api_stack=api,
    auth0_domain=auth0_domain,
    auth0_client_id=auth0_client_id,
    github_oauth_token=github_oauth_token,
    github_owner=github_owner,
    github_repo=github_repo,
    env=env,
)
frontend.add_dependency(api)

# ADR: cdk-nag AwsSolutionsChecks | Enforce AWS security best practices at synth time
cdk.Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(verbose=True))

app.synth()
