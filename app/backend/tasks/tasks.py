"""Celery tasks for async document generation and knowledge base file processing."""

import os
import json
import uuid
import asyncio
from datetime import datetime
from tasks.celery_app import celery_app
from core.database import SessionLocal
from core.encryption import decrypt_api_key
from models.models import (
    User, LLMConfig, KBDocument, DocumentChunk, Document,
    GenerationTask, KnowledgeBase, WordTemplate
)
from services.llm_client import LLMClient
from services.file_parser import parse_file, chunk_text
from services.generation import GenerationPipeline, determine_procurement_method_en
from services.word_renderer import TemplateRenderer


@celery_app.task(name="process_kb_document")
def process_kb_document(doc_id: str):
    """Parse a knowledge base document: extract text, chunk, embed, and index."""
    db = SessionLocal()
    try:
        doc = db.query(KBDocument).filter(KBDocument.id == doc_id).first()
        if not doc:
            return {"error": "Document not found"}

        doc.status = "parsing"
        db.commit()

        # Parse file
        if not doc.file_path or not os.path.exists(doc.file_path):
            doc.status = "failed"
            doc.error_message = "File not found"
            db.commit()
            return {"error": "File not found"}

        pages = parse_file(doc.file_path)
        full_text = "\n".join(p["text"] for p in pages)
        doc.content = full_text

        # Chunk text
        chunks = chunk_text(full_text, chunk_size=500, overlap=50)
        if not chunks:
            doc.status = "failed"
            doc.error_message = "No text content extracted"
            db.commit()
            return {"error": "No text content"}

        # Get user's active LLM config for embeddings
        llm_config = db.query(LLMConfig).filter(
            LLMConfig.user_id == doc.user_id,
            LLMConfig.is_active == True
        ).first()
        if not llm_config:
            doc.status = "failed"
            doc.error_message = "No active LLM config for embeddings"
            db.commit()
            return {"error": "No active LLM config"}

        # Initialize LLM client
        api_key = decrypt_api_key(llm_config.api_key_encrypted)
        llm = LLMClient(
            provider=llm_config.provider,
            api_key=api_key,
            chat_model=llm_config.chat_model,
            api_url=llm_config.api_url,
            embedding_model=llm_config.embedding_model,
            embedding_url=llm_config.embedding_url,
        )

        doc.status = "indexing"
        db.commit()

        # Embed and store chunks
        for i, chunk_text_content in enumerate(chunks):
            try:
                embed_resp = llm.embed(chunk_text_content)
                chunk = DocumentChunk(
                    doc_id=doc.id,
                    chunk_index=i,
                    content=chunk_text_content,
                    embedding=str(embed_resp.vector),
                )
                db.add(chunk)
                db.commit()
            except Exception as e:
                print(f"Failed to embed chunk {i}: {e}")
                continue

        # Update document status
        doc.status = "done"
        doc.meta = {"chunk_count": len(chunks), "pages": len(pages)}
        db.commit()

        return {"status": "done", "chunks": len(chunks)}

    except Exception as e:
        db.rollback()
        try:
            doc = db.query(KBDocument).filter(KBDocument.id == doc_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
                db.commit()
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="generate_document")
def generate_document(task_id: str):
    """Run the full document generation pipeline."""
    db = SessionLocal()
    try:
        task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
        if not task:
            return {"error": "Task not found"}

        document = db.query(Document).filter(Document.id == task.document_id).first()
        if not document:
            task.status = "failed"
            task.error_message = "Document not found"
            db.commit()
            return {"error": "Document not found"}

        # Get user's active LLM config
        llm_config = db.query(LLMConfig).filter(
            LLMConfig.user_id == task.user_id,
            LLMConfig.is_active == True
        ).first()
        if not llm_config:
            task.status = "failed"
            task.error_message = "No active LLM config"
            db.commit()
            return {"error": "No active LLM config"}

        api_key = decrypt_api_key(llm_config.api_key_encrypted)
        llm = LLMClient(
            provider=llm_config.provider,
            api_key=api_key,
            chat_model=llm_config.chat_model,
            api_url=llm_config.api_url,
            embedding_model=llm_config.embedding_model,
            embedding_url=llm_config.embedding_url,
        )

        # Update task status
        task.status = "running"
        task.started_at = datetime.utcnow()
        task.progress = 5
        task.current_step = "intent"
        db.commit()

        # Determine KB IDs to search
        kb_ids = document.source_kb_ids if document.source_kb_ids else []
        # If no specific KBs, get all accessible ones
        if not kb_ids:
            company_kbs = db.query(KnowledgeBase).filter(
                KnowledgeBase.level == "company"
            ).all()
            personal_kbs = db.query(KnowledgeBase).filter(
                KnowledgeBase.user_id == task.user_id,
                KnowledgeBase.level == "personal"
            ).all()
            kb_ids = [str(kb.id) for kb in company_kbs + personal_kbs]

        # Build doc config
        doc_config = {
            "title": document.title,
            "doc_category": document.doc_category or "procurement",
            "procurement_scenario": document.procurement_scenario or "",
            "budget_amount": document.budget_amount or 0,
            "key_elements": document.generation_config.get("key_elements", {}) if document.generation_config else {},
        }

        # Run pipeline
        pipeline = GenerationPipeline(llm, db, str(task.user_id))

        # Step 1: Intent
        task.progress = 15
        task.current_step = "intent"
        db.commit()
        intent = pipeline.analyze_intent(doc_config)

        # Update procurement method if budget was provided
        if document.budget_amount:
            document.procurement_method = determine_procurement_method_en(document.budget_amount)
            db.commit()

        # Step 2: RAG
        task.progress = 30
        task.current_step = "rag"
        db.commit()
        search_query = doc_config["title"] + " " + " ".join(
            str(v) for v in doc_config["key_elements"].values()
        )
        rag_results = pipeline.rag_search(search_query, kb_ids)

        # Step 3: Outline
        task.progress = 45
        task.current_step = "outline"
        db.commit()
        outline = pipeline.generate_outline(doc_config, rag_results)

        # Step 4: Generate sections
        task.progress = 60
        task.current_step = "generate"
        db.commit()
        sections = {}
        section_names = ["事由段落", "依据段落", "请示事项段落"]
        for i, section in enumerate(section_names):
            sections[section] = pipeline.generate_section(
                section, outline, doc_config, rag_results
            )
            task.progress = 60 + (i + 1) * 10
            db.commit()

        full_content = "\n\n".join(sections.values())

        # Step 5: Validate references
        task.progress = 90
        task.current_step = "validate"
        db.commit()
        validation = pipeline.validate_references(
            full_content, rag_results.get("all", [])
        )

        # Save results
        task.progress = 95
        task.current_step = "format"
        db.commit()

        document.content = full_content
        document.status = "done"

        task.result_content = full_content
        task.progress = 100
        task.status = "completed"
        task.current_step = "done"
        task.completed_at = datetime.utcnow()
        task.references = rag_results.get("all", [])[:10]
        db.commit()

        return {"status": "completed", "content": full_content[:200]}

    except Exception as e:
        db.rollback()
        try:
            task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.commit()
            doc = db.query(Document).filter(Document.id == task.document_id).first() if task else None
            if doc:
                doc.status = "failed"
                db.commit()
        except Exception:
            pass
        return {"error": str(e)}
    finally:
        db.close()
