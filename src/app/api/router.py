from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_document_service
from app.schemas.document import DocumentResponse
from app.services.document import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "/search",
    response_model=list[DocumentResponse],
    summary="Return up to 20 matching documents, newest first",
    responses={
        422: {
            "description": "Query cannot be empty or whitespace-only",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                        "required": ["detail"],
                    }
                }
            },
        },
        503: {"description": "Storage temporarily unavailable"},
    },
)
async def search_documents(
    q: str = Query(..., min_length=1, description="Text search query"),
    document_service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    if not q.strip():
        raise HTTPException(status_code=422, detail="Query must contain non-whitespace characters")
    documents = await document_service.search(query=q.strip())

    return [DocumentResponse.model_validate(document) for document in documents]


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"description": "Document not found"},
        503: {"description": "Deletion pending retry"},
    },
)
async def delete_document(
    document_id: int,
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    deleted = await document_service.delete(document_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
