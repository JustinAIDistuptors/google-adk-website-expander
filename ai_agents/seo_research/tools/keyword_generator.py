#!/usr/bin/env python3
"""
Keyword Generator Tool for the SEO Research Agent.

This module provides tools for generating keyword sets for target services
and locations, including primary, secondary, and long-tail variations.
"""

import os
import json
import logging
import random
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class KeywordGenerator:
    """
    Tool for generating keyword sets for target services and locations.
    
    In a production environment, this would connect to a keyword research API like
    SEMrush, Ahrefs, or Google Keyword Planner. For this implementation, we use
    algorithmic generation and templates for demonstration purposes.
    """
    
    def __init__(self, keywords_dir: str = "data/seo_research/keywords"):
        """
        Initialize the Keyword Generator.
        
        Args:
            keywords_dir: Directory for storing keyword data
        """
        self.keywords_dir = keywords_dir
        self.intents = {
            "informational": ["how to", "what is", "ways to", "guide", "tips for"],
            "navigational": ["near me", "in {location}", "local", "nearby", "{location}"],
            "transactional": ["hire", "cost", "price", "quotes", "estimate", "book", "service"],
            "commercial": ["best", "top", "reviews", "compare", "vs", "versus"]
        }
        self.modifiers = {
            "quality": ["professional", "expert", "licensed", "certified", "experienced", "reliable", "trusted"],
            "price": ["affordable", "cheap", "low cost", "budget", "expensive", "premium", "luxury"],
            "time": ["24/7", "emergency", "same day", "fast", "quick", "immediate", "urgent"],
            "service": ["service", "company", "contractor", "specialist", "pro", "technician", "expert"]
        }
        
        os.makedirs(keywords_dir, exist_ok=True)
    
    def generate_keywords(self, service: str, location: Optional[str] = None, 
                         include_serp_data: bool = True) -> Dict[str, Any]:
        """
        Generate keyword sets for a given service and location.
        
        Args:
            service: Service type (e.g., "plumber")
            location: Optional location specifier (e.g., "New York" or "33442")
            include_serp_data: Whether to incorporate SERP analysis data
            
        Returns:
            dict: Generated keyword sets
        """
        # Check for cached results
        cache_key = self._generate_cache_key(service, location)
        cached_result = self._check_cache(cache_key)
        
        if cached_result:
            logger.info(f"Using cached keywords for {service} in {location}")
            return cached_result
        
        logger.info(f"Generating keywords for {service} in {location}")
        
        # Generate keyword sets
        primary_keywords = self._generate_primary_keywords(service, location)
        secondary_keywords = self._generate_secondary_keywords(service, location)
        long_tail_keywords = self._generate_long_tail_keywords(service, location)
        related_keywords = self._generate_related_keywords(service)
        
        # Organize results
        results = {
            "service": service,
            "location": location,
            "primary_keywords": primary_keywords,
            "secondary_keywords": secondary_keywords,
            "long_tail_keywords": long_tail_keywords,
            "related_keywords": related_keywords,
            "keyword_categories": {
                "informational": self._generate_intent_keywords(service, location, "informational"),
                "navigational": self._generate_intent_keywords(service, location, "navigational"),
                "transactional": self._generate_intent_keywords(service, location, "transactional"),
                "commercial": self._generate_intent_keywords(service, location, "commercial")
            }
        }
        
        # Cache the results
        self._cache_results(cache_key, results)
        
        return results
    
    def _generate_cache_key(self, service: str, location: Optional[str]) -> str:
        """
        Generate a cache key for the given parameters.
        
        Args:
            service: Service type
            location: Location specifier
            
        Returns:
            str: Cache key
        """
        service_normalized = service.lower().replace(" ", "_")
        location_part = f"_{location.lower().replace(' ', '_')}" if location else ""
        return f"{service_normalized}{location_part}"
    
    def _check_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Check if results are cached for the given key.
        
        Args:
            cache_key: Cache key
            
        Returns:
            dict: Cached results if available, None otherwise
        """
        cache_path = os.path.join(self.keywords_dir, f"{cache_key}.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading cache for {cache_key}: {str(e)}")
        
        return None
    
    def _cache_results(self, cache_key: str, results: Dict[str, Any]) -> None:
        """
        Cache results for the given key.
        
        Args:
            cache_key: Cache key
            results: Results to cache
        """
        cache_path = os.path.join(self.keywords_dir, f"{cache_key}.json")
        try:
            with open(cache_path, 'w') as f:
                json.dump(results, f, indent=2)
        except Exception as e:
            logger.error(f"Error caching results for {cache_key}: {str(e)}")
    
    def _generate_primary_keywords(self, service: str, location: Optional[str]) -> List[str]:
        """
        Generate primary keyword variations.
        
        Args:
            service: Service type
            location: Location specifier
            
        Returns:
            list: Primary keywords
        """
        primary = [service]
        
        # Add location-specific primary keywords
        if location:
            primary.extend([
                f"{service} {location}",
                f"{service} in {location}",
                f"{location} {service}"
            ])
        else:
            primary.extend([
                f"{service} near me",
                f"local {service}",
                f"{service} services"
            ])
        
        return primary
    
    def _generate_secondary_keywords(self, service: str, location: Optional[str]) -> List[str]:
        """
        Generate secondary keyword variations.
        
        Args:
            service: Service type
            location: Location specifier
            
        Returns:
            list: Secondary keywords
        """
        # Use quality and service modifiers for secondary keywords
        quality_mods = self.modifiers["quality"]
        service_mods = self.modifiers["service"]
        
        secondary = []
        
        # Create combinations
        for quality in random.sample(quality_mods, k=min(3, len(quality_mods))):
            if location:
                secondary.append(f"{quality} {service} in {location}")
                secondary.append(f"{quality} {service} {location}")
            else:
                secondary.append(f"{quality} {service}")
                secondary.append(f"{quality} {service} services")
        
        for svc in random.sample(service_mods, k=min(3, len(service_mods))):
            if location:
                secondary.append(f"{service} {svc} in {location}")
                secondary.append(f"{service} {svc} {location}")
            else:
                secondary.append(f"{service} {svc}")
                secondary.append(f"{service} {svc} near me")
        
        return secondary
    
    def _generate_long_tail_keywords(self, service: str, location: Optional[str]) -> List[str]:
        """
        Generate long-tail keyword variations.
        
        Args:
            service: Service type
            location: Location specifier
            
        Returns:
            list: Long-tail keywords
        """
        # Use more specific patterns for long-tail keywords
        long_tail = []
        
        # Time + Quality + Service + Location
        for time in random.sample(self.modifiers["time"], k=min(2, len(self.modifiers["time"]))):
            for quality in random.sample(self.modifiers["quality"], k=min(2, len(self.modifiers["quality"]))):
                if location:
                    long_tail.append(f"{time} {quality} {service} in {location}")
                else:
                    long_tail.append(f"{time} {quality} {service} near me")
        
        # Price + Service + Location
        for price in random.sample(self.modifiers["price"], k=min(2, len(self.modifiers["price"]))):
            for svc in random.sample(self.modifiers["service"], k=min(2, len(self.modifiers["service"]))):
                if location:
                    long_tail.append(f"{price} {service} {svc} in {location}")
                else:
                    long_tail.append(f"{price} {service} {svc} near me")
        
        # Informational intent + Service + Location
        for info in random.sample(self.intents["informational"], k=min(2, len(self.intents["informational"]))):
            if info == "how to" or info == "what is":
                # These need different sentence structure
                if location:
                    long_tail.append(f"{info} find {service} in {location}")
                    long_tail.append(f"{info} choose {service} in {location}")
                else:
                    long_tail.append(f"{info} find good {service}")
                    long_tail.append(f"{info} choose right {service}")
            else:
                if location:
                    long_tail.append(f"{info} {service} in {location}")
                else:
                    long_tail.append(f"{info} {service}")
        
        # Commercial intent
        for comm in random.sample(self.intents["commercial"], k=min(2, len(self.intents["commercial"]))):
            if location:
                long_tail.append(f"{comm} {service} in {location}")
            else:
                long_tail.append(f"{comm} {service} companies")
        
        # Service-specific variations based on common problems/needs
        if service.lower() == "plumber":
            problems = ["clogged drain", "leaky faucet", "water heater", "toilet repair"]
            for problem in problems:
                if location:
                    long_tail.append(f"{problem} {service} in {location}")
                else:
                    long_tail.append(f"{problem} {service} near me")
        elif service.lower() == "electrician":
            problems = ["power outage", "wiring installation", "ceiling fan", "outlet repair"]
            for problem in problems:
                if location:
                    long_tail.append(f"{problem} {service} in {location}")
                else:
                    long_tail.append(f"{problem} {service} near me")
        
        return long_tail
    
    def _generate_related_keywords(self, service: str) -> List[str]:
        """
        Generate related keywords for the service.
        
        Args:
            service: Service type
            
        Returns:
            list: Related keywords
        """
        # Service-specific related terms
        related = []
        
        if service.lower() == "plumber":
            related = ["plumbing", "plumbing services", "water leak", "drain cleaning", 
                      "pipe repair", "water heater installation", "bathroom plumbing"]
        elif service.lower() == "electrician":
            related = ["electrical services", "wiring", "electrical repair", 
                      "circuit breaker", "lighting installation", "outlet installation"]
        elif service.lower() == "hvac":
            related = ["air conditioning", "heating", "furnace repair", 
                      "ac installation", "duct cleaning", "heat pump"]
        elif service.lower() == "roofer":
            related = ["roof repair", "roofing", "roof replacement", 
                      "shingle repair", "roof inspection", "roof leak"]
        else:
            # Generic related terms
            related = [
                f"{service} repair", 
                f"{service} installation", 
                f"{service} maintenance", 
                f"{service} company", 
                f"{service} contractor"
            ]
        
        return related
    
    def _generate_intent_keywords(self, service: str, location: Optional[str], intent: str) -> List[str]:
        """
        Generate keywords for a specific search intent.
        
        Args:
            service: Service type
            location: Location specifier
            intent: Search intent category
            
        Returns:
            list: Intent-specific keywords
        """
        intent_keywords = []
        
        for pattern in self.intents[intent]:
            if pattern == "in {location}" and location:
                intent_keywords.append(f"{service} in {location}")
            elif pattern == "{location}" and location:
                intent_keywords.append(f"{service} {location}")
            else:
                pattern_replaced = pattern.replace("{location}", location or "")
                if not pattern_replaced.strip():
                    continue
                    
                if pattern in ["how to", "what is", "ways to"]:
                    intent_keywords.append(f"{pattern} find {service}" + (f" in {location}" if location else ""))
                else:
                    intent_keywords.append(f"{service} {pattern_replaced}".strip())
        
        return intent_keywords

# Create a tool function for ADK
def create_keyword_generation_tool():
    """
    Create a keyword generation tool function for the ADK agent.
    
    Returns:
        callable: Keyword generation tool function
    """
    generator = KeywordGenerator()
    
    def keyword_generation_tool(service: str, location: str = None) -> Dict[str, Any]:
        """
        Generates keyword sets for the given service and location.
        
        Args:
            service: Service type (e.g., "plumber")
            location: Optional location to target (e.g., "33442")
            
        Returns:
            dict: Generated keyword sets
        """
        return generator.generate_keywords(service, location)
    
    return keyword_generation_tool
