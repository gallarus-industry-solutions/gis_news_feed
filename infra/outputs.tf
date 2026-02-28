# File: infra/outputs.tf
# Outputs for reference and downstream automation.

output "lambda_function_name" {
  description = "Name of the deployed Lambda function."
  value       = aws_lambda_function.news_bot.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function."
  value       = aws_lambda_function.news_bot.arn
}

output "schedule_expression" {
  description = "EventBridge schedule expression."
  value       = var.schedule_expression
}

output "log_group" {
  description = "CloudWatch log group for Lambda logs."
  value       = aws_cloudwatch_log_group.lambda.name
}
