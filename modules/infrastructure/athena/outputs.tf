output "workgroup_names" {
  description = "Map of short name to full Athena workgroup name"
  value       = { for name, wg in aws_athena_workgroup.workgroup : name => wg.name }
}
