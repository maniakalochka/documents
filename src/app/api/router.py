from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.dependencies import get_document_service
from app.schemas.document import DocumentResponse
from app.services.document import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/search", response_model=list[DocumentResponse])
async def search_documents(
    q: str = Query(..., min_length=1, description="Text search query"),
    limit: int = Query(20, ge=1, le=20),
    document_service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    documents = await document_service.search(query=q, limit=limit)

    return [DocumentResponse.model_validate(document) for document in documents]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    document_service: DocumentService = Depends(get_document_service),
) -> Response:
    deleted = await document_service.delete(document_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    return Response(status_code=status.HTTP_204_NO_CONTENT)
