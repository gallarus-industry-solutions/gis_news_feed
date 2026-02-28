# File: infra/main.tf
# Core infrastructure for the Gallarus Intelligence Bulletin Lambda.
#
# Resources:
#   - SSM Parameter Store entries for secrets
#   - IAM role + policy for Lambda execution
#   - Lambda function
#   - EventBridge scheduled rule
#   - CloudWatch log group

locals {
  function_name = "${var.project_name}-${var.environment}"
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# ---------------------------------------------------------------------------
# SSM Parameter Store — secrets stored securely, injected as env vars
# ---------------------------------------------------------------------------

resource "aws_ssm_parameter" "gemini_api_key" {
  name  = "/${var.project_name}/${var.environment}/GEMINI_API_KEY"
  type  = "SecureString"
  value = var.gemini_api_key
  tags  = local.tags
}

resource "aws_ssm_parameter" "teams_webhook_url" {
  name  = "/${var.project_name}/${var.environment}/TEAMS_WEBHOOK_URL"
  type  = "SecureString"
  value = var.teams_webhook_url
  tags  = local.tags
}

resource "aws_ssm_parameter" "news_api_key" {
  name  = "/${var.project_name}/${var.environment}/NEWS_API_KEY"
  type  = "SecureString"
  value = var.news_api_key
  tags  = local.tags
}

resource "aws_ssm_parameter" "youtube_api_key" {
  name  = "/${var.project_name}/${var.environment}/YOUTUBE_API_KEY"
  type  = "SecureString"
  value = var.youtube_api_key
  tags  = local.tags
}

# ---------------------------------------------------------------------------
# IAM — Lambda execution role
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.function_name}-lambda-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "lambda_permissions" {
  # CloudWatch Logs
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${local.function_name}:*"]
  }

  # SSM Parameter Store — read-only access to our secrets
  statement {
    effect  = "Allow"
    actions = ["ssm:GetParameter", "ssm:GetParameters"]
    resources = [
      "arn:aws:ssm:${var.aws_region}:*:parameter/${var.project_name}/${var.environment}/*",
    ]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${local.function_name}-lambda-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda_permissions.json
}

# ---------------------------------------------------------------------------
# CloudWatch Log Group — explicit to control retention
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 14
  tags              = local.tags
}

# ---------------------------------------------------------------------------
# Lambda Function
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "news_bot" {
  function_name = local.function_name
  description   = "Gallarus Intelligence Bulletin — daily AI news digest to Teams"

  # Deployment package — built by scripts/build_lambda.sh
  filename         = "${path.module}/../dist/lambda_package.zip"
  source_code_hash = filebase64sha256("${path.module}/../dist/lambda_package.zip")
  handler          = "lambda_handler.handler"
  runtime          = var.lambda_runtime
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_mb

  role = aws_iam_role.lambda.arn

  environment {
    variables = {
      GEMINI_API_KEY   = var.gemini_api_key
      TEAMS_WEBHOOK_URL = var.teams_webhook_url
      NEWS_API_KEY     = var.news_api_key
      YOUTUBE_API_KEY  = var.youtube_api_key
      # Lambda writable path for cache file
      CACHE_DIR        = "/tmp/data"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy.lambda,
  ]

  tags = local.tags
}

# ---------------------------------------------------------------------------
# EventBridge — scheduled trigger
# ---------------------------------------------------------------------------

resource "aws_scheduler_schedule" "daily_digest" {
  name       = "${local.function_name}-daily"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_lambda_function.news_bot.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn
    input    = jsonencode({ source = "scheduled" })
  }
}

# IAM role for EventBridge Scheduler to invoke Lambda
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge_scheduler" {
  name               = "${local.function_name}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
  tags               = local.tags
}

data "aws_iam_policy_document" "scheduler_invoke" {
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.news_bot.arn]
  }
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name   = "${local.function_name}-scheduler-invoke"
  role   = aws_iam_role.eventbridge_scheduler.id
  policy = data.aws_iam_policy_document.scheduler_invoke.json
}
