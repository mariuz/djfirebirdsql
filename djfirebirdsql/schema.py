from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from .cursor import FirebirdCursorWrapper, _quote_value     # NOQA isort:skip


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    sql_rename_table = "Rename table is not allowed"  # Not supported
    sql_delete_table = "DROP TABLE %(table)s"
    sql_create_column = "ALTER TABLE %(table)s ADD %(column)s %(definition)s"
    sql_alter_column_type = "ALTER %(column)s TYPE %(type)s"
    sql_alter_column_default = "ALTER COLUMN %(column)s SET DEFAULT %(default)s"
    sql_alter_column_no_default = "ALTER COLUMN %(column)s DROP DEFAULT"
    sql_delete_column = "ALTER TABLE %(table)s DROP %(column)s"
    sql_rename_column = "ALTER TABLE %(table)s ALTER %(old_column)s TO %(new_column)s"
    sql_create_fk = "ALTER TABLE %(table)s ADD CONSTRAINT %(name)s FOREIGN KEY (%(column)s) REFERENCES %(to_table)s (%(to_column)s) ON DELETE CASCADE"
    sql_delete_fk = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"
    sql_pk_to_unique = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s, ADD CONSTRAINT %(name)s UNIQUE (%(column)s)"
    sql_unique_to_pk = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s, ADD CONSTRAINT %(name)s PRIMARY KEY (%(column)s)"
    sql_delete_constraint = "ALTER TABLE %(table)s DROP CONSTRAINT %(name)s"
    sql_add_identity = "ALTER TABLE %(table)s ALTER COLUMN %(column)s SET GENERATED BY DEFAULT"
    sql_delete_identity = "ALTER TABLE %(table)s ALTER COLUMN %(column)s DROP IDENTITY"
    sql_create_index = 'CREATE INDEX %(name)s ON %(table)s (%(columns)s)%(extra)s'

    def quote_value(self, value):
        return _quote_value(value)

    def prepare_default(self, value):
        return self.quote_value(value)

    def _get_field_indexes(self, model, field):
        return self.connection.introspection._get_field_indexes(model._meta.db_table, field.column)

    def _alter_column_type_sql(self, model, old_field, new_field, new_type):
        if new_field.get_internal_type() == 'AutoField':
            new_type = 'integer'
        elif new_field.get_internal_type() == 'BigAutoField':
            new_type = 'bigint'
        elif new_field.get_internal_type() == 'SmallAutoField':
            new_type = 'smallint'
        return super()._alter_column_type_sql(model, old_field, new_field, new_type)

    def _alter_field(self, model, old_field, new_field, old_type, new_type,
                     old_db_params, new_db_params, strict=False):
        if (old_field.get_internal_type() in ('AutoField', 'BigAutoField', 'SmallAutoField')
            and new_field.get_internal_type() not in ('AutoField', 'BigAutoField', 'SmallAutoField')):
            self.execute(self.sql_delete_identity % {
                'table': self.quote_name(model._meta.db_table),
                'column': self.quote_name(old_field.column),
            })

        super()._alter_field(model, old_field, new_field, old_type, new_type,
                     old_db_params, new_db_params)

        if (old_field.get_internal_type() not in ('AutoField', 'BigAutoField', 'SmallAutoField') and
            new_field.get_internal_type() in ('AutoField', 'BigAutoField', 'SmallAutoField')):
            self.execute(self.sql_add_identity % {
                'table': self.quote_name(model._meta.db_table),
                'column': self.quote_name(old_field.column),
            })

    def delete_model(self, model):
        """Delete a model from the database."""
        # delete related foreign key constraints
        for r in self.connection.introspection._get_references(model._meta.db_table):
            self.execute(self.sql_delete_fk % {'name': r[0], 'table': r[1].upper()})
        super().delete_model(model)

    def _column_has_default(self, params):
        sql = """
            SELECT a.RDB$DEFAULT_VALUE
            FROM RDB$RELATION_FIELDS a
            WHERE UPPER(a.RDB$FIELD_NAME) = UPPER('%(column)s')
            AND UPPER(a.RDB$RELATION_NAME) = UPPER('%(table_name)s')
        """
        value = self.execute(sql % params)
        return True if value else False

    def _column_sql(self, model, field):
        """
        Take a field and return its column definition.
        The field must already have had set_attributes_from_name() called.
        """
        # Get the column's type and use that as the basis of the SQL
        db_params = field.db_parameters(connection=self.connection)
        sql = db_params['type']

        # Primary key/unique outputs
        if field.primary_key:
            sql += " PRIMARY KEY"
        elif field.unique:
            sql += " UNIQUE"

        # Return the sql
        return sql
