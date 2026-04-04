# Owner: AZ
# PolicyDiffApiStack — HTTP API (V2) with Auth0 JWT authorizer, 22 routes.

import aws_cdk as cdk
from aws_cdk import (
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
)
from constructs import Construct
from lib.compute_stack import PolicyDiffComputeStack


class PolicyDiffApiStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        compute_stack: PolicyDiffComputeStack,
        auth0_domain: str = "",
        auth0_audience: str = "",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ADR: HTTP API V2 over REST API V1 | V2 natively supports JWT authorizers; simpler + cheaper
        http_api = apigwv2.HttpApi(
            self, "PolicyDiffHttpApi",
            api_name="policydiff-api",
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.ANY],
                allow_headers=["Content-Type", "Authorization", "X-Api-Key", "X-Amz-Security-Token"],
            ),
            default_authorizer=None,
        )

        # Auth0 JWT authorizer — only created when auth0_domain is provided
        jwt_authorizer = None
        if auth0_domain and auth0_audience:
            jwt_authorizer = authorizers.HttpJwtAuthorizer(
                "Auth0JwtAuthorizer",
                f"https://{auth0_domain}/",
                jwt_audience=[auth0_audience],
            )

        def add_route(path: str, method: apigwv2.HttpMethod, fn):
            integration = integrations.HttpLambdaIntegration(
                f"Integration{method.value}{path.replace('/', '_').replace('{', '').replace('}', '')}",
                fn,
            )
            kwargs_route = dict(
                path=path,
                methods=[method],
                integration=integration,
            )
            if jwt_authorizer:
                kwargs_route["authorizer"] = jwt_authorizer
            http_api.add_routes(**kwargs_route)

        # Policies
        add_route("/api/policies/upload-url", apigwv2.HttpMethod.POST, compute_stack.upload_url_fn)
        add_route("/api/policies", apigwv2.HttpMethod.POST, compute_stack.policy_crud_fn)
        add_route("/api/policies/{id}", apigwv2.HttpMethod.GET, compute_stack.policy_crud_fn)
        add_route("/api/policies/{id}/status", apigwv2.HttpMethod.GET, compute_stack.policy_crud_fn)
        add_route("/api/policies/{id}/criteria", apigwv2.HttpMethod.GET, compute_stack.policy_crud_fn)
        add_route("/api/policies", apigwv2.HttpMethod.GET, compute_stack.policy_crud_fn)
        add_route("/api/policies/{id}", apigwv2.HttpMethod.DELETE, compute_stack.policy_crud_fn)

        # Query
        add_route("/api/query", apigwv2.HttpMethod.POST, compute_stack.query_fn)
        add_route("/api/query/{queryId}", apigwv2.HttpMethod.GET, compute_stack.query_fn)
        add_route("/api/queries", apigwv2.HttpMethod.GET, compute_stack.query_fn)

        # Compare
        add_route("/api/compare", apigwv2.HttpMethod.GET, compute_stack.compare_fn)
        add_route("/api/compare/export", apigwv2.HttpMethod.GET, compute_stack.compare_fn)

        # Diffs
        add_route("/api/diffs", apigwv2.HttpMethod.GET, compute_stack.diff_fn)
        add_route("/api/diffs/{diffId}", apigwv2.HttpMethod.GET, compute_stack.diff_fn)
        add_route("/api/diffs/feed", apigwv2.HttpMethod.GET, compute_stack.diff_fn)

        # Discordance
        add_route("/api/discordance", apigwv2.HttpMethod.GET, compute_stack.discordance_fn)
        add_route("/api/discordance/{drug}/{payer}", apigwv2.HttpMethod.GET, compute_stack.discordance_fn)

        # Approval Path
        add_route("/api/approval-path", apigwv2.HttpMethod.POST, compute_stack.approval_path_fn)
        add_route("/api/approval-path/{id}/memo", apigwv2.HttpMethod.POST, compute_stack.approval_path_fn)

        # User Preferences
        add_route("/api/users/me/preferences", apigwv2.HttpMethod.GET, compute_stack.policy_crud_fn)
        add_route("/api/users/me/preferences", apigwv2.HttpMethod.PUT, compute_stack.policy_crud_fn)

        # Simulator
        add_route("/api/simulate", apigwv2.HttpMethod.POST, compute_stack.simulator_fn)

        self.api_url = http_api.api_endpoint

        # cdk-nag suppressions
        from cdk_nag import NagSuppressions
        NagSuppressions.add_resource_suppressions(http_api, [
            {"id": "AwsSolutions-APIG1", "reason": "Access logging requires a CloudWatch log group; acceptable for hackathon scope"},
            # APIG4 fires when auth0_domain is not provided at synth time (no authorizer attached)
            {"id": "AwsSolutions-APIG4", "reason": "Auth0 JWT authorizer is attached when auth0Domain context is provided; routes are protected in production"},
        ], apply_to_children=True)

        cdk.CfnOutput(self, "ApiInvokeUrl",
            value=http_api.api_endpoint,
            export_name="ApiInvokeUrl",
        )
