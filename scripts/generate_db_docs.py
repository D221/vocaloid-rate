# Assuming app.models is importable from the project root
# Add the project root to the sys.path
import sys
from pathlib import Path

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import RelationshipProperty

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Playlist, PlaylistTrack, Rating, Track, UpdateLog


def generate_model_markdown(model_class):
    inspector = sa_inspect(model_class)
    table_name = model_class.__tablename__

    markdown = f"## {model_class.__name__} Model\n\n"
    markdown += f"**Table Name:** `{table_name}`\n\n"

    if model_class.__doc__:
        markdown += f"### Description\n{model_class.__doc__.strip()}\n\n"

    markdown += "### Columns\n\n"
    markdown += "| Column Name | Type | Primary Key | Nullable | Default |\n"
    markdown += "|-------------|------|-------------|----------|---------|\n"

    for column in inspector.columns:
        col_name = column.name
        col_type = str(column.type)
        col_pk = "Yes" if column.primary_key else "No"
        col_nullable = "Yes" if column.nullable else "No"
        col_default = ""

        if column.default:
            # If the default is a callable function (like now()), use its name
            if callable(column.default.arg):
                if column.default.arg.__name__ == "now":
                    col_default = "Current Timestamp"
                else:
                    # For other functions, show it's a function call
                    col_default = f"func.{column.default.arg.__name__}"
            else:
                # Otherwise, it's a static value
                col_default = str(column.default.arg)

        markdown += f"| `{col_name}` | `{col_type}` | {col_pk} | {col_nullable} | {col_default} |\n"
    markdown += "\n"

    relationships = [
        p
        for p in inspector.mapper.iterate_properties
        if isinstance(p, RelationshipProperty)
    ]
    if relationships:
        markdown += "### Relationships\n\n"
        markdown += "| Relationship Name | Related Model | Type | Back Populates |\n"
        markdown += "|-------------------|---------------|------|----------------|\n"
        for rel in relationships:
            rel_name = rel.key
            rel_model = rel.mapper.class_.__name__
            rel_type = "Many-to-One" if rel.uselist is False else "One-to-Many"
            rel_back_populates = rel.back_populates if rel.back_populates else ""
            markdown += f"| `{rel_name}` | `{rel_model}` | {rel_type} | `{rel_back_populates}` |\n"
        markdown += "\n"

    return markdown


def generate_all_db_docs(output_path: Path):
    all_models = [Track, Rating, UpdateLog, PlaylistTrack, Playlist]

    full_markdown = "# Database Schema Reference\n\n"
    full_markdown += "This document provides an automatically generated reference for the database schema.\n\n"

    for model_class in all_models:
        full_markdown += generate_model_markdown(model_class)
        full_markdown += "---\n\n"  # Separator between models

    output_path.write_text(full_markdown, encoding="utf-8")
    print(f"Generated database schema documentation to {output_path}")


if __name__ == "__main__":
    output_file = Path("docs/docs/database-schema.md")
    generate_all_db_docs(output_file)
