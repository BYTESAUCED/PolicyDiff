# Owner: AZ
# PolicyDiffStorageStack — S3 bucket, S3 Vectors bucket + index, 6 DynamoDB tables.

import aws_cdk as cdk
from aws_cdk import (
    aws_s3 as s3,
    aws_dynamodb as dynamodb,
    aws_s3vectors as s3vectors,
)
from constructs import Construct


class PolicyDiffStorageStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # S3 bucket for raw policy PDFs and Textract output
        self.policy_bucket = s3.Bucket(
            self,
            "DocumentsBucket",
            bucket_name=f"policydiff-documents-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}",
            versioned=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            event_bridge_enabled=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=cdk.Duration.days(30),
                        )
                    ],
                )
            ],
        )

        # PolicyDocuments table — PK: policyDocId
        self.policy_documents_table = dynamodb.Table(
            self,
            "PolicyDocumentsTable",
            table_name="PolicyDocuments",
            partition_key=dynamodb.Attribute(
                name="policyDocId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        self.policy_documents_table.add_global_secondary_index(
            index_name="payerName-effectiveDate-index",
            partition_key=dynamodb.Attribute(
                name="payerName", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="effectiveDate", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # DrugPolicyCriteria table — PK: policyDocId, SK: drugIndicationId
        self.drug_policy_criteria_table = dynamodb.Table(
            self,
            "DrugPolicyCriteriaTable",
            table_name="DrugPolicyCriteria",
            partition_key=dynamodb.Attribute(
                name="policyDocId", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="drugIndicationId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        self.drug_policy_criteria_table.add_global_secondary_index(
            index_name="drugName-payerName-index",
            partition_key=dynamodb.Attribute(
                name="drugName", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="payerName", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )
        self.drug_policy_criteria_table.add_global_secondary_index(
            index_name="drugName-effectiveDate-index",
            partition_key=dynamodb.Attribute(
                name="drugName", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="effectiveDate", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # PolicyDiffs table — PK: diffId
        self.policy_diffs_table = dynamodb.Table(
            self,
            "PolicyDiffsTable",
            table_name="PolicyDiffs",
            partition_key=dynamodb.Attribute(
                name="diffId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        self.policy_diffs_table.add_global_secondary_index(
            index_name="drugName-diffType-index",
            partition_key=dynamodb.Attribute(
                name="drugName", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="diffType", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # QueryLog table — PK: queryId
        self.query_log_table = dynamodb.Table(
            self,
            "QueryLogTable",
            table_name="QueryLog",
            partition_key=dynamodb.Attribute(
                name="queryId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # ApprovalPaths table — PK: approvalPathId
        self.approval_paths_table = dynamodb.Table(
            self,
            "ApprovalPathsTable",
            table_name="ApprovalPaths",
            partition_key=dynamodb.Attribute(
                name="approvalPathId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # UserPreferences table — PK: userId (Auth0 sub claim)
        self.user_preferences_table = dynamodb.Table(
            self,
            "UserPreferencesTable",
            table_name="UserPreferences",
            partition_key=dynamodb.Attribute(
                name="userId", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # ADR: S3 Vectors L1 construct | aws_s3vectors L2 not yet available; CfnVectorBucket is the only option
        self.vectors_bucket = s3vectors.CfnVectorBucket(
            self, "VectorsBucket",
            vector_bucket_name=f"policydiff-vectors-{cdk.Aws.ACCOUNT_ID}-{cdk.Aws.REGION}",
        )

        self.vectors_index = s3vectors.CfnIndex(
            self, "PolicyCriteriaIndex",
            vector_bucket_name=self.vectors_bucket.ref,
            index_name="policy-criteria-index",
            data_type="float32",
            dimension=1536,
            distance_metric="cosine",
        )
        self.vectors_index.add_dependency(self.vectors_bucket)

        # CloudFormation exports
        cdk.CfnOutput(self, "DocumentsBucketArn", value=self.policy_bucket.bucket_arn, export_name="DocumentsBucketArn")
        cdk.CfnOutput(self, "DocumentsBucketName", value=self.policy_bucket.bucket_name, export_name="DocumentsBucketName")
        cdk.CfnOutput(self, "VectorsBucketName", value=self.vectors_bucket.ref, export_name="VectorsBucketName")

        cdk.CfnOutput(self, "PolicyDocumentsTableName", value=self.policy_documents_table.table_name, export_name="PolicyDocumentsTableName")
        cdk.CfnOutput(self, "PolicyDocumentsTableArn", value=self.policy_documents_table.table_arn, export_name="PolicyDocumentsTableArn")

        cdk.CfnOutput(self, "DrugPolicyCriteriaTableName", value=self.drug_policy_criteria_table.table_name, export_name="DrugPolicyCriteriaTableName")
        cdk.CfnOutput(self, "DrugPolicyCriteriaTableArn", value=self.drug_policy_criteria_table.table_arn, export_name="DrugPolicyCriteriaTableArn")

        cdk.CfnOutput(self, "PolicyDiffsTableName", value=self.policy_diffs_table.table_name, export_name="PolicyDiffsTableName")
        cdk.CfnOutput(self, "PolicyDiffsTableArn", value=self.policy_diffs_table.table_arn, export_name="PolicyDiffsTableArn")

        cdk.CfnOutput(self, "QueryLogTableName", value=self.query_log_table.table_name, export_name="QueryLogTableName")
        cdk.CfnOutput(self, "QueryLogTableArn", value=self.query_log_table.table_arn, export_name="QueryLogTableArn")

        cdk.CfnOutput(self, "ApprovalPathsTableName", value=self.approval_paths_table.table_name, export_name="ApprovalPathsTableName")
        cdk.CfnOutput(self, "ApprovalPathsTableArn", value=self.approval_paths_table.table_arn, export_name="ApprovalPathsTableArn")

        cdk.CfnOutput(self, "UserPreferencesTableName", value=self.user_preferences_table.table_name, export_name="UserPreferencesTableName")
        cdk.CfnOutput(self, "UserPreferencesTableArn", value=self.user_preferences_table.table_arn, export_name="UserPreferencesTableArn")
