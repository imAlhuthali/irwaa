import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import aiofiles
import os
from pathlib import Path
import hashlib
import mimetypes

from models import get_database_manager

logger = logging.getLogger(__name__)

class ContentService:
    """Service for managing educational content and weekly materials"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self.content_dir = Path("content")
        self.uploads_dir = Path("uploads")
        
        # Create directories if they don't exist
        self.content_dir.mkdir(exist_ok=True)
        self.uploads_dir.mkdir(exist_ok=True)
        
        # Supported file types
        self.supported_file_types = {
            '.pdf', '.doc', '.docx', '.ppt', '.pptx', 
            '.txt', '.md', '.jpg', '.jpeg', '.png', 
            '.mp4', '.mp3', '.zip', '.rar'
        }
        
        # Max file size (50MB)
        self.max_file_size = 50 * 1024 * 1024

    async def create_material(self, material_data: Dict[str, Any]) -> int:
        """Create a new educational material"""
        try:
            # Validate required fields
            required_fields = ['title', 'description', 'section', 'subject', 'week_number']
            for field in required_fields:
                if field not in material_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Set default values
            material_data.setdefault('date_published', datetime.now())
            material_data.setdefault('is_active', True)
            material_data.setdefault('content_type', 'text')
            material_data.setdefault('difficulty_level', 'medium')
            material_data.setdefault('estimated_duration', 30)  # minutes
            
            # Generate content hash for duplicate detection
            content_hash = self._generate_content_hash(material_data)
            material_data['content_hash'] = content_hash
            
            # Check for duplicates
            existing = await self.db.get_material_by_hash(content_hash)
            if existing:
                logger.warning(f"Duplicate material detected: {material_data['title']}")
                return existing['id']
            
            # Insert into database
            material_id = await self.db.create_material(material_data)
            
            # Create content directory for this material
            material_dir = self.content_dir / str(material_id)
            material_dir.mkdir(exist_ok=True)
            
            logger.info(f"Created material: {material_data['title']} (ID: {material_id})")
            return material_id
            
        except Exception as e:
            logger.error(f"Error creating material: {e}")
            raise

    async def get_weekly_materials(self, section: str, week_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get materials for a specific section and week"""
        try:
            if week_number is None:
                # Get current week number (you can customize this logic)
                week_number = self._get_current_week_number()
            
            materials = await self.db.get_materials_by_section_and_week(section, week_number)
            
            # Enrich materials with additional metadata
            enriched_materials = []
            for material in materials:
                enriched_material = await self._enrich_material_data(material)
                enriched_materials.append(enriched_material)
            
            # Sort by priority and date
            enriched_materials.sort(
                key=lambda x: (x.get('priority', 0), x['date_published']), 
                reverse=True
            )
            
            return enriched_materials
            
        except Exception as e:
            logger.error(f"Error fetching weekly materials: {e}")
            return []

    async def get_material_by_id(self, material_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific material by ID"""
        try:
            material = await self.db.get_material_by_id(material_id)
            if not material:
                return None
            
            return await self._enrich_material_data(material)
            
        except Exception as e:
            logger.error(f"Error fetching material {material_id}: {e}")
            return None

    async def update_material(self, material_id: int, updates: Dict[str, Any]) -> bool:
        """Update an existing material"""
        try:
            # Update content hash if content changed
            if 'content' in updates or 'title' in updates:
                material = await self.db.get_material_by_id(material_id)
                if material:
                    updated_data = {**material, **updates}
                    updates['content_hash'] = self._generate_content_hash(updated_data)
            
            updates['last_modified'] = datetime.now()
            success = await self.db.update_material(material_id, updates)
            
            if success:
                logger.info(f"Updated material {material_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating material {material_id}: {e}")
            return False

    async def delete_material(self, material_id: int) -> bool:
        """Delete a material (soft delete)"""
        try:
            success = await self.db.update_material(material_id, {
                'is_active': False,
                'deleted_at': datetime.now()
            })
            
            if success:
                logger.info(f"Deleted material {material_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting material {material_id}: {e}")
            return False

    async def upload_file(self, material_id: int, file_data: bytes, filename: str) -> Optional[Dict[str, Any]]:
        """Upload and associate a file with a material"""
        try:
            # Validate file
            file_extension = Path(filename).suffix.lower()
            if file_extension not in self.supported_file_types:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            if len(file_data) > self.max_file_size:
                raise ValueError(f"File too large: {len(file_data)} bytes")
            
            # Generate unique filename
            file_hash = hashlib.md5(file_data).hexdigest()
            safe_filename = f"{file_hash}_{filename}"
            
            # Create material directory
            material_dir = self.uploads_dir / str(material_id)
            material_dir.mkdir(exist_ok=True)
            
            file_path = material_dir / safe_filename
            
            # Save file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            
            # Create file record
            file_info = {
                'material_id': material_id,
                'original_filename': filename,
                'stored_filename': safe_filename,
                'file_path': str(file_path),
                'file_size': len(file_data),
                'file_type': file_extension,
                'mime_type': mimetypes.guess_type(filename)[0],
                'upload_date': datetime.now(),
                'file_hash': file_hash
            }
            
            file_id = await self.db.create_material_file(file_info)
            file_info['id'] = file_id
            
            # Update material with file reference
            await self.db.update_material(material_id, {
                'has_files': True,
                'last_modified': datetime.now()
            })
            
            logger.info(f"Uploaded file {filename} for material {material_id}")
            return file_info
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return None

    async def get_material_files(self, material_id: int) -> List[Dict[str, Any]]:
        """Get all files associated with a material"""
        try:
            return await self.db.get_material_files(material_id)
        except Exception as e:
            logger.error(f"Error fetching files for material {material_id}: {e}")
            return []

    async def get_file_content(self, file_id: int) -> Optional[bytes]:
        """Get file content by file ID"""
        try:
            file_info = await self.db.get_material_file_by_id(file_id)
            if not file_info:
                return None
            
            file_path = Path(file_info['file_path'])
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            async with aiofiles.open(file_path, 'rb') as f:
                return await f.read()
                
        except Exception as e:
            logger.error(f"Error reading file {file_id}: {e}")
            return None

    async def search_materials(self, query: str, section: Optional[str] = None, 
                             subject: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search materials by query"""
        try:
            materials = await self.db.search_materials(query, section, subject, limit)
            
            # Enrich search results
            enriched_results = []
            for material in materials:
                enriched_material = await self._enrich_material_data(material)
                enriched_results.append(enriched_material)
            
            return enriched_results
            
        except Exception as e:
            logger.error(f"Error searching materials: {e}")
            return []

    async def get_materials_by_subject(self, subject: str, section: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get materials by subject"""
        try:
            materials = await self.db.get_materials_by_subject(subject, section)
            
            enriched_materials = []
            for material in materials:
                enriched_material = await self._enrich_material_data(material)
                enriched_materials.append(enriched_material)
            
            return enriched_materials
            
        except Exception as e:
            logger.error(f"Error fetching materials by subject: {e}")
            return []

    async def get_recent_materials(self, section: str, days: int = 7) -> List[Dict[str, Any]]:
        """Get materials published in the last N days"""
        try:
            since_date = datetime.now() - timedelta(days=days)
            materials = await self.db.get_materials_since_date(section, since_date)
            
            enriched_materials = []
            for material in materials:
                enriched_material = await self._enrich_material_data(material)
                enriched_materials.append(enriched_material)
            
            return enriched_materials
            
        except Exception as e:
            logger.error(f"Error fetching recent materials: {e}")
            return []

    async def get_content_statistics(self) -> Dict[str, Any]:
        """Get content statistics"""
        try:
            stats = await self.db.get_content_statistics()
            return {
                'total_materials': stats.get('total_materials', 0),
                'materials_by_section': stats.get('materials_by_section', {}),
                'materials_by_subject': stats.get('materials_by_subject', {}),
                'total_files': stats.get('total_files', 0),
                'total_file_size': stats.get('total_file_size', 0),
                'recent_uploads': stats.get('recent_uploads', 0)
            }
        except Exception as e:
            logger.error(f"Error fetching content statistics: {e}")
            return {}

    async def publish_weekly_batch(self, section: str, week_number: int, materials: List[Dict[str, Any]]) -> List[int]:
        """Publish a batch of materials for a specific week"""
        created_materials = []
        
        try:
            for material_data in materials:
                material_data.update({
                    'section': section,
                    'week_number': week_number,
                    'date_published': datetime.now(),
                    'is_active': True
                })
                
                material_id = await self.create_material(material_data)
                created_materials.append(material_id)
            
            logger.info(f"Published {len(created_materials)} materials for {section}, week {week_number}")
            return created_materials
            
        except Exception as e:
            logger.error(f"Error publishing weekly batch: {e}")
            # Rollback created materials
            for material_id in created_materials:
                await self.delete_material(material_id)
            return []

    def _generate_content_hash(self, material_data: Dict[str, Any]) -> str:
        """Generate hash for content deduplication"""
        content_string = f"{material_data.get('title', '')}{material_data.get('content', '')}{material_data.get('section', '')}"
        return hashlib.sha256(content_string.encode()).hexdigest()

    async def _enrich_material_data(self, material: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich material data with additional metadata"""
        try:
            # Add file information
            files = await self.get_material_files(material['id'])
            material['files'] = files
            material['file_count'] = len(files)
            
            # Add view statistics if available
            view_stats = await self.db.get_material_view_stats(material['id'])
            material['view_count'] = view_stats.get('view_count', 0)
            material['unique_viewers'] = view_stats.get('unique_viewers', 0)
            
            # Calculate content metrics
            content_length = len(material.get('content', ''))
            material['content_length'] = content_length
            material['estimated_read_time'] = max(1, content_length // 200)  # ~200 words per minute
            
            # Add relative time
            now = datetime.now()
            pub_date = material['date_published']
            if isinstance(pub_date, str):
                pub_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
            
            time_diff = now - pub_date
            if time_diff.days > 0:
                material['relative_time'] = f"منذ {time_diff.days} يوم"
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                material['relative_time'] = f"منذ {hours} ساعة"
            else:
                minutes = max(1, time_diff.seconds // 60)
                material['relative_time'] = f"منذ {minutes} دقيقة"
            
            return material
            
        except Exception as e:
            logger.error(f"Error enriching material data: {e}")
            return material

    def _get_current_week_number(self) -> int:
        """Get current academic week number"""
        # This is a simple implementation - you can customize based on your academic calendar
        now = datetime.now()
        # Assuming academic year starts in September
        if now.month >= 9:
            start_date = datetime(now.year, 9, 1)
        else:
            start_date = datetime(now.year - 1, 9, 1)
        
        week_number = ((now - start_date).days // 7) + 1
        return max(1, min(week_number, 36))  # Academic year typically has ~36 weeks

    async def cleanup_old_files(self, days_old: int = 90) -> int:
        """Clean up files older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            old_files = await self.db.get_files_older_than(cutoff_date)
            
            deleted_count = 0
            for file_info in old_files:
                try:
                    file_path = Path(file_info['file_path'])
                    if file_path.exists():
                        file_path.unlink()
                    
                    await self.db.delete_material_file(file_info['id'])
                    deleted_count += 1
                    
                except Exception as e:
                    logger.error(f"Error deleting file {file_info['id']}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old files")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during file cleanup: {e}")
            return 0