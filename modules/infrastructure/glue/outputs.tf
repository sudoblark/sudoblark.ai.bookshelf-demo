output "database_names" {
  description = "Map of database short name to full Glue catalog database name"
  value       = { for name, db in aws_glue_catalog_database.database : name => db.name }
}

output "crawler_names" {
  description = "Map of crawler short name to full Glue crawler name"
  value       = { for name, c in aws_glue_crawler.crawler : name => c.name }
}
