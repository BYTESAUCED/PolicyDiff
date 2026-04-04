# Owner: AZ
# PolicyDiffFrontendStack — Amplify App (L1 CfnApp) for React + Vite frontend.

import aws_cdk as cdk
from aws_cdk import aws_amplify as amplify
from constructs import Construct
from lib.api_stack import PolicyDiffApiStack

_BUILD_SPEC = "\n".join([
    "version: 1",
    "frontend:",
    "  phases:",
    "    preBuild:",
    "      commands:",
    "        - cd frontend && npm ci",
    "    build:",
    "      commands:",
    "        - npm run build",
    "  artifacts:",
    "    baseDirectory: frontend/dist",
    "    files:",
    '      - "**/*"',
    "  cache:",
    "    paths:",
    "      - frontend/node_modules/**/*",
])


class PolicyDiffFrontendStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        api_stack: PolicyDiffApiStack,
        auth0_domain: str = "",
        auth0_client_id: str = "",
        github_oauth_token: str = "",
        github_owner: str = "PLACEHOLDER",
        github_repo: str = "policydiff",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if not auth0_client_id:
            import warnings
            warnings.warn("auth0_client_id is empty — VITE_AUTH0_CLIENT_ID will not be set in Amplify", stacklevel=2)

        # ADR: github_oauth_token from .env via app.py | Never hardcode tokens
        github_token = github_oauth_token or "PLACEHOLDER"
        repo_url = f"https://github.com/{github_owner}/{github_repo}"

        # ADR: CfnApp (L1) over aws_amplify_alpha | alpha module not in stable aws-cdk-lib 2.x
        amplify_app = amplify.CfnApp(
            self, "PolicyDiffAmplifyApp",
            name="policydiff-frontend",
            repository=repo_url,
            oauth_token=github_token,
            platform="WEB",
            build_spec=_BUILD_SPEC,
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_API_BASE_URL",
                    value=api_stack.api_url,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_AUTH0_DOMAIN",
                    value=auth0_domain,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="VITE_AUTH0_CLIENT_ID",
                    value=auth0_client_id,
                ),
            ],
        )

        amplify.CfnBranch(
            self, "MainBranch",
            app_id=amplify_app.attr_app_id,
            branch_name="main",
            enable_auto_build=True,
            stage="PRODUCTION",
        )

        amplify_domain = f"main.{amplify_app.attr_app_id}.amplifyapp.com"

        cdk.CfnOutput(self, "AmplifyAppDomain",
            value=amplify_domain,
            export_name="AmplifyAppDomain",
        )
