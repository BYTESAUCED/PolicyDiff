# Owner: AZ
# PolicyDiffComputeStack — Lambda functions, Step Functions, EventBridge rules, IAM roles.

import os
import platform
import aws_cdk as cdk
from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
)
from constructs import Construct
from cdk_nag import NagSuppressions
from lib.storage_stack import PolicyDiffStorageStack

BEDROCK_MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5"


class PolicyDiffComputeStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        storage_stack: PolicyDiffStorageStack,
        bedrock_model_arn: str = "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-5",
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ADR: bedrock_model_arn from .env via app.py | Never hardcode model ARNs
        BEDROCK_MODEL_ARN = bedrock_model_arn

        # ADR: Dynamic arch detection | Supports Apple Silicon and Intel Macs
        host_arch = platform.machine()
        lambda_arch = (
            lambda_.Architecture.ARM_64
            if host_arch == "arm64"
            else lambda_.Architecture.X86_64
        )

        lambda_code = lambda_.Code.from_asset(
            os.path.join(os.path.dirname(__file__), "..", "lambda")
        )

        common_env = {
            "DOCUMENTS_BUCKET_NAME": storage_stack.policy_bucket.bucket_name,
            "POLICY_DOCUMENTS_TABLE": storage_stack.policy_documents_table.table_name,
            "DRUG_POLICY_CRITERIA_TABLE": storage_stack.drug_policy_criteria_table.table_name,
            "POLICY_DIFFS_TABLE": storage_stack.policy_diffs_table.table_name,
            "QUERY_LOG_TABLE": storage_stack.query_log_table.table_name,
            "APPROVAL_PATHS_TABLE": storage_stack.approval_paths_table.table_name,
            "USER_PREFERENCES_TABLE": storage_stack.user_preferences_table.table_name,
            "REGION": cdk.Aws.REGION,
        }

        # ── Lambda definitions ────────────────────────────────────────────────

        self.upload_url_fn = lambda_.Function(
            self, "UploadUrlLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="upload_url.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(10),
            memory_size=256,
            environment=common_env,
        )

        self.policy_crud_fn = lambda_.Function(
            self, "PolicyCrudLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="policy_crud.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            environment=common_env,
        )

        self.policy_monitor_fn = lambda_.Function(
            self, "PolicyMonitorLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="policy_monitor.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(60),
            memory_size=256,
            environment=common_env,
        )

        self.query_fn = lambda_.Function(
            self, "QueryLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="query.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(60),
            memory_size=512,
            environment=common_env,
        )

        self.compare_fn = lambda_.Function(
            self, "CompareLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="compare.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(60),
            memory_size=512,
            environment=common_env,
        )

        self.diff_fn = lambda_.Function(
            self, "DiffLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="diff.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(120),
            memory_size=512,
            environment=common_env,
        )

        self.discordance_fn = lambda_.Function(
            self, "DiscordanceLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="discordance.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(60),
            memory_size=512,
            environment=common_env,
        )

        self.approval_path_fn = lambda_.Function(
            self, "ApprovalPathLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="approval_path.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(90),
            memory_size=512,
            environment=common_env,
        )

        self.simulator_fn = lambda_.Function(
            self, "SimulatorLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="simulator.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(60),
            memory_size=512,
            environment=common_env,
        )

        TITAN_EMBED_ARN = "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"

        self.embed_index_fn = lambda_.Function(
            self, "EmbedAndIndexLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="embed_and_index.lambda_handler",
            code=lambda_code,
            architecture=lambda_arch,
            timeout=cdk.Duration.seconds(120),
            memory_size=512,
            environment={
                **common_env,
                "VECTORS_BUCKET_NAME": storage_stack.vectors_bucket.ref,
                "TITAN_MODEL_ARN": TITAN_EMBED_ARN,
            },
        )

        # ── IAM grants ───────────────────────────────────────────────────────

        # UploadUrlLambda
        storage_stack.policy_bucket.grant_put(self.upload_url_fn)
        storage_stack.policy_documents_table.grant_write_data(self.upload_url_fn)
        NagSuppressions.add_resource_suppressions(self.upload_url_fn, [
            {"id": "AwsSolutions-IAM5", "reason": "S3 object-level access requires key prefix wildcard"},
        ], apply_to_children=True)

        # PolicyCrudLambda
        storage_stack.policy_documents_table.grant_read_write_data(self.policy_crud_fn)
        storage_stack.drug_policy_criteria_table.grant_read_write_data(self.policy_crud_fn)
        storage_stack.user_preferences_table.grant_read_write_data(self.policy_crud_fn)

        # PolicyMonitorLambda — grant_read covers s3:GetObject + s3:ListBucket
        storage_stack.policy_bucket.grant_read(self.policy_monitor_fn)
        storage_stack.policy_bucket.grant_put(self.policy_monitor_fn)
        # ADR: Explicit s3:DeleteObject + s3:CopyObject | No CDK grant method for these
        self.policy_monitor_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["s3:DeleteObject", "s3:CopyObject"],
            resources=[f"{storage_stack.policy_bucket.bucket_arn}/*"],
        ))
        NagSuppressions.add_resource_suppressions(self.policy_monitor_fn, [
            {"id": "AwsSolutions-IAM5", "reason": "S3 object-level access requires key prefix wildcard"},
        ], apply_to_children=True)

        # QueryLambda
        storage_stack.drug_policy_criteria_table.grant_read_data(self.query_fn)
        storage_stack.policy_documents_table.grant_read_data(self.query_fn)
        storage_stack.query_log_table.grant_read_data(self.query_fn)
        storage_stack.policy_diffs_table.grant_read_data(self.query_fn)
        storage_stack.query_log_table.grant_write_data(self.query_fn)
        self.query_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[BEDROCK_MODEL_ARN],
        ))

        # CompareLambda
        storage_stack.drug_policy_criteria_table.grant_read_data(self.compare_fn)
        self.compare_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[BEDROCK_MODEL_ARN],
        ))

        # DiffLambda
        storage_stack.drug_policy_criteria_table.grant_read_data(self.diff_fn)
        storage_stack.policy_diffs_table.grant_read_data(self.diff_fn)
        storage_stack.policy_diffs_table.grant_write_data(self.diff_fn)
        self.diff_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[BEDROCK_MODEL_ARN],
        ))

        # DiscordanceLambda
        storage_stack.drug_policy_criteria_table.grant_read_data(self.discordance_fn)
        storage_stack.policy_diffs_table.grant_read_data(self.discordance_fn)

        # ApprovalPathLambda
        storage_stack.drug_policy_criteria_table.grant_read_data(self.approval_path_fn)
        storage_stack.policy_documents_table.grant_read_data(self.approval_path_fn)
        storage_stack.approval_paths_table.grant_write_data(self.approval_path_fn)
        self.approval_path_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[BEDROCK_MODEL_ARN],
        ))

        # SimulatorLambda
        storage_stack.drug_policy_criteria_table.grant_read_data(self.simulator_fn)

        # EmbedAndIndexLambda
        storage_stack.policy_bucket.grant_read(self.embed_index_fn)
        self.embed_index_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[TITAN_EMBED_ARN],
        ))
        self.embed_index_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["s3vectors:PutVectors"],
            resources=[f"arn:aws:s3vectors:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:bucket/policydiff-vectors-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}/index/policy-criteria-index"],
        ))
        NagSuppressions.add_resource_suppressions(self.embed_index_fn, [
            {"id": "AwsSolutions-IAM4", "reason": "AWSLambdaBasicExecutionRole is the minimal required managed policy for Lambda CloudWatch logging"},
            {"id": "AwsSolutions-L1", "reason": "python3.12 is the latest stable Lambda runtime used per project standards"},
            {"id": "AwsSolutions-IAM5", "reason": "S3 object-level access requires key prefix wildcard"},
        ], apply_to_children=True)

        # QueryLambda — S3 Vectors semantic search + Titan embeddings for query-time embedding
        self.query_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["s3vectors:QueryVectors"],
            resources=[f"arn:aws:s3vectors:{cdk.Aws.REGION}:{cdk.Aws.ACCOUNT_ID}:bucket/policydiff-vectors-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}/index/policy-criteria-index"],
        ))

        # ── ExtractionWorkflow execution role ────────────────────────────────

        workflow_role = iam.Role(
            self, "ExtractionWorkflowRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )
        storage_stack.policy_bucket.grant_read_write(workflow_role)
        storage_stack.policy_documents_table.grant_read_write_data(workflow_role)
        storage_stack.drug_policy_criteria_table.grant_read_write_data(workflow_role)
        # ADR: Textract wildcard resource | Textract does not support resource-level permissions
        workflow_role.add_to_policy(iam.PolicyStatement(
            actions=["textract:StartDocumentAnalysis", "textract:GetDocumentAnalysis"],
            resources=["*"],
        ))
        workflow_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=[BEDROCK_MODEL_ARN],
        ))
        # Allow Step Functions to invoke Lambda functions used in the workflow
        for fn in [self.diff_fn]:
            fn.grant_invoke(workflow_role)

        NagSuppressions.add_resource_suppressions(workflow_role, [
            {"id": "AwsSolutions-IAM5", "reason": "Textract does not support resource-level permissions"},
        ], apply_to_children=True)

        # ── Step Functions states ─────────────────────────────────────────────

        start_textract = sfn_tasks.CallAwsService(
            self, "StartTextractJob",
            service="textract",
            action="startDocumentAnalysis",
            parameters={
                "DocumentLocation": {
                    "S3Object": {
                        "Bucket": sfn.JsonPath.string_at("$.bucketName"),
                        "Name": sfn.JsonPath.string_at("$.s3Key"),
                    }
                },
                "FeatureTypes": ["TABLES", "FORMS"],
            },
            result_path="$.textractResult",
            iam_resources=["*"],
        )

        poll_textract = sfn_tasks.CallAwsService(
            self, "PollTextractJob",
            service="textract",
            action="getDocumentAnalysis",
            parameters={
                "JobId": sfn.JsonPath.string_at("$.textractResult.JobId"),
            },
            result_path="$.pollResult",
            iam_resources=["*"],
        )

        wait_for_textract = sfn.Wait(
            self, "WaitForTextract",
            time=sfn.WaitTime.duration(cdk.Duration.seconds(10)),
        )

        textract_complete = sfn.Choice(self, "TextractComplete")
        textract_succeeded = sfn.Condition.string_equals(
            "$.pollResult.JobStatus", "SUCCEEDED"
        )
        textract_failed = sfn.Condition.string_equals(
            "$.pollResult.JobStatus", "FAILED"
        )

        extraction_failed = sfn.Fail(
            self, "ExtractionFailed",
            cause="Textract job failed or timed out",
            error="TextractJobFailed",
        )

        assemble_text = sfn_tasks.LambdaInvoke(
            self, "AssembleStructuredText",
            lambda_function=self.policy_crud_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path="$.assembleResult",
            payload_response_only=True,
        )

        bedrock_extraction = sfn_tasks.LambdaInvoke(
            self, "BedrockSchemaExtraction",
            lambda_function=self.query_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path="$.extractionResult",
            payload_response_only=True,
        )

        confidence_scoring = sfn_tasks.LambdaInvoke(
            self, "ConfidenceScoring",
            lambda_function=self.compare_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path="$.scoringResult",
            payload_response_only=True,
        )

        write_to_dynamo = sfn_tasks.LambdaInvoke(
            self, "WriteToDynamoDB",
            lambda_function=self.policy_crud_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path="$.writeResult",
            payload_response_only=True,
        )

        execution_complete = sfn.Succeed(self, "ExecutionComplete")

        invoke_diff_async = sfn_tasks.LambdaInvoke(
            self, "InvokeDiffAsync",
            lambda_function=self.diff_fn,
            invocation_type=sfn_tasks.LambdaInvocationType.EVENT,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path=sfn.JsonPath.DISCARD,
        )

        trigger_diff_choice = sfn.Choice(self, "TriggerDiffIfVersionExists")
        has_previous_version = sfn.Condition.is_present("$.previousVersionId")

        # State 6.5 — EmbedAndIndex (non-blocking: catches all errors and continues)
        embed_and_index = sfn_tasks.LambdaInvoke(
            self, "EmbedAndIndex",
            lambda_function=self.embed_index_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path="$.embedResult",
            payload_response_only=True,
        )
        embed_and_index.add_catch(
            trigger_diff_choice,
            errors=["States.ALL"],
            result_path="$.embedError",
        )
        # Wire polling loop with retry
        poll_textract.add_retry(
            errors=["States.ALL"],
            interval=cdk.Duration.seconds(10),
            max_attempts=30,
            backoff_rate=1.0,
        )

        poll_loop = (
            textract_complete
            .when(textract_succeeded, assemble_text)
            .when(textract_failed, extraction_failed)
            .otherwise(wait_for_textract.next(poll_textract))
        )

        diff_branch = (
            trigger_diff_choice
            .when(has_previous_version, invoke_diff_async.next(execution_complete))
            .otherwise(execution_complete)
        )

        definition = sfn.Chain.start(
            start_textract
            .next(poll_textract)
            .next(textract_complete)
        )
        # Chain after poll_loop resolves to assemble_text path
        assemble_text.next(bedrock_extraction)
        bedrock_extraction.next(confidence_scoring)
        confidence_scoring.next(write_to_dynamo)
        write_to_dynamo.next(embed_and_index)
        embed_and_index.next(trigger_diff_choice)

        # ADR: Express Workflow | Cost-effective for short-lived executions (<5 min)
        self.extraction_workflow = sfn.StateMachine(
            self, "ExtractionWorkflow",
            state_machine_name="PolicyDiffExtractionWorkflow",
            state_machine_type=sfn.StateMachineType.EXPRESS,
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            role=workflow_role,
            timeout=cdk.Duration.minutes(5),
        )

        # Inject workflow ARN into Lambdas that need to start executions
        self.upload_url_fn.add_environment(
            "EXTRACTION_WORKFLOW_ARN", self.extraction_workflow.state_machine_arn
        )
        self.policy_crud_fn.add_environment(
            "EXTRACTION_WORKFLOW_ARN", self.extraction_workflow.state_machine_arn
        )

        # Grant UploadUrlLambda and PolicyCrudLambda permission to start the extraction workflow
        self.extraction_workflow.grant_start_execution(self.upload_url_fn)
        self.extraction_workflow.grant_start_execution(self.policy_crud_fn)

        # ── EventBridge rules ─────────────────────────────────────────────────

        # S3 ObjectCreated on raw/ prefix → ExtractionWorkflow
        extraction_rule = events.Rule(
            self, "ExtractionTriggerRule",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [storage_stack.policy_bucket.bucket_name]},
                    "object": {"key": [{"prefix": "raw/"}]},
                },
            ),
        )
        extraction_rule.add_target(
            targets.SfnStateMachine(self.extraction_workflow)
        )

        # Daily trigger for PolicyMonitorLambda
        monitor_rule = events.Rule(
            self, "ScheduledMonitorRule",
            schedule=events.Schedule.rate(cdk.Duration.days(1)),
        )
        monitor_rule.add_target(targets.LambdaFunction(self.policy_monitor_fn))

        # ── cdk-nag suppressions ─────────────────────────────────────────────

        _lambda_fns = [
            self.upload_url_fn, self.policy_crud_fn, self.policy_monitor_fn,
            self.query_fn, self.compare_fn, self.diff_fn,
            self.discordance_fn, self.approval_path_fn, self.simulator_fn,
            self.embed_index_fn,
        ]

        for fn in _lambda_fns:
            NagSuppressions.add_resource_suppressions(fn, [
                # AWSLambdaBasicExecutionRole is the minimal managed policy for Lambda logging
                {"id": "AwsSolutions-IAM4", "reason": "AWSLambdaBasicExecutionRole is the minimal required managed policy for Lambda CloudWatch logging", "appliesTo": ["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"]},
                # python3.12 is the latest stable runtime; cdk-nag flags it as non-latest due to version check lag
                {"id": "AwsSolutions-L1", "reason": "python3.12 is the latest stable Lambda runtime used per project standards"},
            ], apply_to_children=True)

        # DynamoDB GSI index/* wildcards are generated by CDK grant methods — expected
        _dynamo_gsi_fns = [
            self.policy_crud_fn, self.query_fn, self.compare_fn, self.diff_fn,
            self.discordance_fn, self.approval_path_fn, self.simulator_fn,
        ]
        for fn in _dynamo_gsi_fns:
            NagSuppressions.add_resource_suppressions(fn, [
                {"id": "AwsSolutions-IAM5", "reason": "DynamoDB GSI access requires index/* wildcard; generated by CDK grant methods"},
            ], apply_to_children=True)

        NagSuppressions.add_resource_suppressions(self.extraction_workflow, [
            {"id": "AwsSolutions-SF1", "reason": "CloudWatch logging for Express Workflow adds cost; acceptable for hackathon scope"},
            {"id": "AwsSolutions-SF2", "reason": "X-Ray tracing adds cost; acceptable for hackathon scope"},
        ])

        # ── CloudFormation outputs ────────────────────────────────────────────

        cdk.CfnOutput(self, "ExtractionWorkflowArn",
            value=self.extraction_workflow.state_machine_arn,
            export_name="ExtractionWorkflowArn",
        )
        cdk.CfnOutput(self, "UploadUrlFunctionArn",
            value=self.upload_url_fn.function_arn,
            export_name="UploadUrlFunctionArn",
        )
        cdk.CfnOutput(self, "PolicyCrudFunctionArn",
            value=self.policy_crud_fn.function_arn,
            export_name="PolicyCrudFunctionArn",
        )
        cdk.CfnOutput(self, "QueryFunctionArn",
            value=self.query_fn.function_arn,
            export_name="QueryFunctionArn",
        )
        cdk.CfnOutput(self, "CompareFunctionArn",
            value=self.compare_fn.function_arn,
            export_name="CompareFunctionArn",
        )
        cdk.CfnOutput(self, "DiffFunctionArn",
            value=self.diff_fn.function_arn,
            export_name="DiffFunctionArn",
        )
        cdk.CfnOutput(self, "DiscordanceFunctionArn",
            value=self.discordance_fn.function_arn,
            export_name="DiscordanceFunctionArn",
        )
        cdk.CfnOutput(self, "ApprovalPathFunctionArn",
            value=self.approval_path_fn.function_arn,
            export_name="ApprovalPathFunctionArn",
        )
        cdk.CfnOutput(self, "SimulatorFunctionArn",
            value=self.simulator_fn.function_arn,
            export_name="SimulatorFunctionArn",
        )
        cdk.CfnOutput(self, "EmbedIndexFunctionArn",
            value=self.embed_index_fn.function_arn,
            export_name="EmbedIndexFunctionArn",
        )
