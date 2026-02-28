# File: infra/variables.tf
# Input variables for the Gallarus News Bot infrastructure.

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project identifier used in resource naming."
  type        = string
  default     = "gis-news-feed"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)."
  type        = string
  default     = "prod"
}

variable "schedule_expression" {
  description = "EventBridge cron/rate expression for digest schedule."
  type        = string
  default     = "cron(0 7 ? * MON-FRI *)" # 07:00 UTC, weekdays only
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds."
  type        = number
  default     = 120
}

variable "lambda_memory_mb" {
  description = "Lambda function memory allocation in MB."
  type        = number
  default     = 512
}

variable "lambda_runtime" {
  description = "Lambda runtime version."
  type        = string
  default     = "python3.13"
}

# ---------------------------------------------------------------------------
# Secrets — passed in via CLI, environment, or tfvars.
# Never commit actual values to source control.
# ---------------------------------------------------------------------------

variable "gemini_api_key" {
  description = "Google Gemini API key."
  type        = string
  sensitive   = true
}

variable "teams_webhook_url" {
  description = "Microsoft Teams Incoming Webhook URL."
  type        = string
  sensitive   = true
}

variable "news_api_key" {
  description = "NewsAPI.org API key."
  type        = string
  sensitive   = true
  default     = ""
}

variable "youtube_api_key" {
  description = "YouTube Data API v3 key."
  type        = string
  sensitive   = true
  default     = ""
}
