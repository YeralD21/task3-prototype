"""Response schemas specific to Dataset Registry queries."""

from pydantic import BaseModel, Field

from app.schemas.canonical import CorpusRecord


class CorpusRecordPage(BaseModel):
    """Small offset-based page used by the textual corpus explorer."""

    items: list[CorpusRecord]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
