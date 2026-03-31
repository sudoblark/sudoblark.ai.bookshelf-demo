output "state_machine_arns" {
  description = "Map of state machine short name to ARN"
  value       = { for k, v in aws_sfn_state_machine.state_machine : k => v.arn }
}
