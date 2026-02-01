# services/event_processor.py
"""
Event Processor Service - AI-powered event analysis and enrichment for Opentrace
Processes incoming events with NLP, entity extraction, and intelligent classification.
"""

import asyncio
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import logging

from models.event import Event
from models.person import Person
from models.location import Location
from services.location_resolver import location_resolver
from db.session import async_session

logger = logging.getLogger(__name__)


class EventProcessor:
    """
    Service for processing and enriching events with AI analysis.
    
    Uses NLP techniques to:
    - Extract entities (names, locations, dates, phone numbers)
    - Generate summaries for quick scanning
    - Classify event types and confidence scores
    - Detect duplicates and similar events
    - Analyze sentiment and urgency
    """
    
    def __init__(self):
        # Common patterns for entity extraction
        self.name_patterns = [
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # First Last
            r'\b[A-Z][a-z]+\b',              # Single name
            r'\bMc[A-Z][a-z]+\b',           # Mc/Mac names
            r'\bO\'[A-Z][a-z]+\b',           # O' names
        ]
        
        self.date_patterns = [
            r'\b\d{1,2}\/\d{1,2}\/\d{4}\b',  # MM/DD/YYYY
            r'\b\d{4}-\d{2}-\d{2}\b',       # YYYY-MM-DD
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b',  # Month DD, YYYY
        ]
        
        self.phone_patterns = [
            r'\b\d{3}-\d{3}-\d{4}\b',      # 555-555-5555
            r'\b\(\d{3}\)\s*\d{3}-\d{4}\b', # (555) 555-5555
        ]
        
        self.location_keywords = [
            'street', 'avenue', 'road', 'boulevard', 'lane', 'drive',
            'city', 'town', 'county', 'state', 'country',
            'near', 'at', 'in', 'by', 'around', 'downtown'
        ]
        
        self.urgency_keywords = [
            'urgent', 'emergency', 'immediate', 'critical', 'serious',
            'dangerous', 'harm', 'threat', 'suspicious', 'concerning'
        ]
        
        self.sighting_keywords = [
            'saw', 'seen', 'spotted', 'witness', 'noticed', 'observed',
            'looked like', 'resembled', 'matched', 'appeared'
        ]

    async def process_event(self, event_data: Dict[str, Any]) -> Event:
        """
        Process and enrich an event with AI analysis.
        
        Args:
            event_data: Raw event data from API or ingestion
            
        Returns:
            Enriched Event object with AI analysis
        """
        try:
            logger.info(f"Processing event: {event_data.get('title', 'Unknown')}")
            
            # Extract entities from text
            entities = await self._extract_entities(event_data)
            
            # Generate summary
            summary = await self._generate_summary(event_data, entities)
            
            # Classify event type and confidence
            event_type, confidence = await self._classify_event(event_data, entities)
            
            # Analyze sentiment
            sentiment = await self._analyze_sentiment(event_data)
            
            # Determine priority
            priority = await self._determine_priority(event_data, entities, sentiment)
            
            # Create Event object
            event = Event(
                pfif_id=event_data['pfif_id'],
                location_id=event_data.get('location_id'),
                event_type=event_type,
                event_subtype=event_data.get('event_subtype'),
                event_date=self._parse_date(event_data.get('event_date')),
                title=event_data.get('title'),
                description=event_data.get('description'),
                summary=summary,
                source_type=event_data.get('source_type', 'user_submitted'),
                source_url=event_data.get('source_url'),
                source_confidence=event_data.get('source_confidence', 'medium'),
                is_verified=event_data.get('is_verified', False),
                evidence_count=len(event_data.get('evidence', [])),
                has_media=any(e.get('type') in ['photo', 'video', 'audio'] for e in event_data.get('evidence', [])),
                location_description=event_data.get('location_description'),
                location_precision=event_data.get('location_precision', 'unknown'),
                reporter_name=event_data.get('reporter_name'),
                reporter_contact=event_data.get('reporter_contact'),
                witness_count=event_data.get('witness_count', 0),
                priority=priority,
                created_by=event_data.get('created_by', 'event_processor'),
                tags=event_data.get('tags', []),
                ai_processed=True,
                ai_confidence=confidence,
                ai_entities=entities,
                ai_sentiment=sentiment,
                is_public=event_data.get('is_public', True),
                access_level=event_data.get('access_level', 'public')
            )
            
            # Save to database
            async with async_session() as db:
                db.add(event)
                await db.commit()
                await db.refresh(event)
            
            logger.info(f"Processed event {event.event_id}: {event_type} (confidence: {confidence})")
            return event
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            raise

    async def _extract_entities(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities from event text using NLP patterns."""
        entities = {
            'names': [],
            'locations': [],
            'dates': [],
            'phone_numbers': [],
            'emails': [],
            'keywords': []
        }
        
        text = f"{event_data.get('title', '')} {event_data.get('description', '')}"
        
        # Extract names
        for pattern in self.name_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            entities['names'].extend(matches)
        
        # Extract dates
        for pattern in self.date_patterns:
            matches = re.findall(pattern, text)
            entities['dates'].extend(matches)
        
        # Extract phone numbers
        for pattern in self.phone_patterns:
            matches = re.findall(pattern, text)
            entities['phone_numbers'].extend(matches)
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        entities['emails'].extend(matches)
        
        # Extract location keywords
        for keyword in self.location_keywords:
            if keyword.lower() in text.lower():
                entities['keywords'].append(keyword)
        
        # Extract urgency keywords
        for keyword in self.urgency_keywords:
            if keyword.lower() in text.lower():
                entities['keywords'].append(keyword)
        
        # Extract sighting keywords
        for keyword in self.sighting_keywords:
            if keyword.lower() in text.lower():
                entities['keywords'].append(keyword)
        
        # Remove duplicates and clean
        for key in entities:
            entities[key] = list(set(entities[key]))
        
        return entities

    async def _generate_summary(self, event_data: Dict[str, Any], entities: Dict[str, Any]) -> str:
        """Generate AI-powered summary for quick scanning."""
        try:
            title = event_data.get('title', '')
            description = event_data.get('description', '')
            event_type = event_data.get('event_type', '')
            
            # Create base summary
            summary_parts = []
            
            if title:
                summary_parts.append(title)
            
            # Add event type context
            type_context = {
                'sighting': 'Possible sighting reported',
                'police_report': 'Police report filed',
                'status_change': 'Status update provided',
                'tip': 'Community tip submitted',
                'document': 'Document evidence submitted',
                'recovery': 'Recovery information'
            }
            
            if event_type in type_context:
                summary_parts.append(type_context[event_type])
            
            # Add key entities
            if entities.get('names'):
                names = entities['names'][:2]  # Limit to first 2 names
                if len(names) == 1:
                    summary_parts.append(f"Involving {names[0]}")
                else:
                    summary_parts.append(f"Involving {names[0]} and {names[1]}")
            
            if entities.get('locations'):
                locations = entities['locations'][:2]
                summary_parts.append(f"Location: {', '.join(locations)}")
            
            # Add urgency if detected
            if entities.get('keywords'):
                urgent_keywords = [k for k in entities['keywords'] if k in self.urgency_keywords]
                if urgent_keywords:
                    summary_parts.append(f"Urgent: {', '.join(urgent_keywords)}")
            
            # Add witness count if available
            witness_count = event_data.get('witness_count', 0)
            if witness_count > 0:
                summary_parts.append(f"{witness_count} witness{'es' if witness_count != 1 else ''}")
            
            # Add evidence count
            evidence_count = event_data.get('evidence_count', 0)
            if evidence_count > 0:
                summary_parts.append(f"{evidence_count} attachment{'s' if evidence_count != 1 else ''}")
            
            # Truncate if too long
            full_summary = '. '.join(summary_parts)
            if len(full_summary) > 200:
                full_summary = full_summary[:197] + "..."
            
            return full_summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return event_data.get('title', 'Event processed')[:100]

    async def _classify_event(self, event_data: Dict[str, Any], entities: Dict[str, Any]) -> Tuple[str, float]:
        """Classify event type and confidence score."""
        try:
            # Base classification from provided type
            base_type = event_data.get('event_type', 'tip')
            
            # Confidence scoring factors
            confidence_factors = []
            
            # Source reliability
            source_confidence = event_data.get('source_confidence', 'medium')
            source_scores = {'high': 0.9, 'medium': 0.7, 'low': 0.5}
            confidence_factors.append(source_scores.get(source_confidence, 0.7))
            
            # Has evidence
            if event_data.get('evidence_count', 0) > 0:
                confidence_factors.append(0.8)
            
            # Has verified reporter
            if event_data.get('reporter_name'):
                confidence_factors.append(0.7)
            
            # Has location
            if event_data.get('location_id') or event_data.get('location_description'):
                confidence_factors.append(0.6)
            
            # Keywords match
            if entities.get('keywords'):
                keyword_score = min(len(entities['keywords']) * 0.1, 0.3)
                confidence_factors.append(keyword_score)
            
            # Description length (longer descriptions often more detailed)
            description_length = len(event_data.get('description', ''))
            if description_length > 100:
                confidence_factors.append(0.6)
            elif description_length > 50:
                confidence_factors.append(0.4)
            
            # Calculate average confidence
            if confidence_factors:
                avg_confidence = sum(confidence_factors) / len(confidence_factors)
            else:
                avg_confidence = 0.5
            
            # Adjust based on event type patterns
            text = f"{event_data.get('title', '')} {event_data.get('description', '')}".lower()
            
            # Boost confidence for clear event type indicators
            if base_type == 'sighting' and any(word in text for word in self.sighting_keywords):
                avg_confidence = min(avg_confidence + 0.2, 1.0)
            elif base_type == 'police_report' and 'police' in text:
                avg_confidence = min(avg_confidence + 0.3, 1.0)
            elif base_type == 'status_change' and 'status' in text:
                avg_confidence = min(avg_confidence + 0.2, 1.0)
            
            return base_type, round(avg_confidence, 2)
            
        except Exception as e:
            logger.error(f"Error classifying event: {e}")
            return event_data.get('event_type', 'tip'), 0.5

    async def _analyze_sentiment(self, event_data: Dict[str, Any]) -> str:
        """Analyze sentiment of event content."""
        try:
            text = f"{event_data.get('title', '')} {event_data.get('description', '')}".lower()
            
            # Simple keyword-based sentiment analysis
            positive_words = ['found', 'safe', 'recovered', 'identified', 'located', 'helpful', 'good']
            negative_words = ['missing', 'lost', 'danger', 'harm', 'threat', 'scary', 'worry', 'concern']
            
            positive_count = sum(1 for word in positive_words if word in text)
            negative_count = sum(1 for word in negative_words if word in text)
            
            if positive_count > negative_count * 1.5:
                return 'positive'
            elif negative_count > positive_count * 1.5:
                return 'negative'
            else:
                return 'neutral'
                
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return 'neutral'

    async def _determine_priority(self, event_data: Dict[str, Any], entities: Dict[str, Any], sentiment: str) -> str:
        """Determine event priority based on content and analysis."""
        try:
            # Base priority
            base_priority = event_data.get('priority', 'medium')
            
            # Priority factors
            priority_score = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
            current_score = priority_score.get(base_priority, 2)
            
            # Urgency keywords increase priority
            if entities.get('keywords'):
                urgent_keywords = [k for k in entities['keywords'] if k in self.urgency_keywords]
                current_score += len(urgent_keywords)
            
            # Negative sentiment increases priority
            if sentiment == 'negative':
                current_score += 1
            
            # Police reports are higher priority
            if event_data.get('source_type') == 'police_report':
                current_score += 1
            
            # Recent events (last 24 hours) are higher priority
            event_date = self._parse_date(event_data.get('event_date'))
            if event_date:
                time_diff = datetime.utcnow() - event_date.replace(tzinfo=None)
                if time_diff.days == 0:
                    current_score += 1
            
            # Convert back to priority level
            if current_score >= 4:
                return 'critical'
            elif current_score >= 3:
                return 'high'
            elif current_score >= 2:
                return 'medium'
            else:
                return 'low'
                
        except Exception as e:
            logger.error(f"Error determining priority: {e}")
            return event_data.get('priority', 'medium')

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string into datetime object."""
        if not date_str:
            return None
            
        # Try different date formats
        date_formats = [
            '%Y-%m-%d',      # 2024-01-15
            '%m/%d/%Y',      # 01/15/2024
            '%B %d, %Y',    # January 15, 2024
            '%b %d, %Y',    # Jan 15, 2024
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try ISO format
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            pass
        
        return None

    async def detect_duplicates(self, event: Event) -> List[Event]:
        """Find similar events that might be duplicates."""
        try:
            async with async_session() as db:
                # Query for potentially duplicate events
                query = select(Event).where(
                    Event.pfif_id == event.pfif_id,
                    Event.event_id != event.event_id,
                    Event.event_status == 'active'
                )
                
                result = await db.execute(query)
                potential_duplicates = result.scalars().all()
                
                duplicates = []
                
                for potential in potential_duplicates:
                    similarity_score = await self._calculate_similarity(event, potential)
                    if similarity_score > 0.7:  # 70% similarity threshold
                        duplicates.append(potential)
                
                return duplicates
                
        except Exception as e:
            logger.error(f"Error detecting duplicates: {e}")
            return []

    async def _calculate_similarity(self, event1: Event, event2: Event) -> float:
        """Calculate similarity score between two events."""
        try:
            score = 0.0
            
            # Event type similarity
            if event1.event_type == event2.event_type:
                score += 0.3
            
            # Time proximity (within 24 hours)
            if event1.event_date and event2.event_date:
                time_diff = abs((event1.event_date - event2.event_date).total_seconds())
                if time_diff <= 86400:  # 24 hours
                    score += 0.3
                elif time_diff <= 604800:  # 7 days
                    score += 0.1
            
            # Location similarity
            if event1.location_id and event1.location_id == event2.location_id:
                score += 0.2
            
            # Description similarity (simple text overlap)
            if event1.description and event2.description:
                desc1_words = set(event1.description.lower().split())
                desc2_words = set(event2.description.lower().split())
                if desc1_words and desc2_words:
                    overlap = len(desc1_words & desc2_words)
                    union = len(desc1_words | desc2_words)
                    if union > 0:
                        score += (overlap / union) * 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0


# Singleton instance
event_processor = EventProcessor()
