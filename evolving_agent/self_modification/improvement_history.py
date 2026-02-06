"""
Improvement history tracking system for self-modification.
Tracks all improvements with timestamps, success/failure rates, and impact metrics.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logging import setup_logger

logger = setup_logger(__name__)


class ImprovementRecord:
    """Represents a single improvement attempt."""
    
    def __init__(
        self,
        improvement_id: str,
        improvement_type: str,
        file_path: str,
        original_code_hash: str,
        modified_code_hash: str,
        rationale: str,
        priority: float,
        status: str = "pending",  # pending, approved, applied, failed, rolled_back
        validation_result: Optional[Dict[str, Any]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        impact_metrics: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.improvement_id = improvement_id
        self.improvement_type = improvement_type
        self.file_path = file_path
        self.original_code_hash = original_code_hash
        self.modified_code_hash = modified_code_hash
        self.rationale = rationale
        self.priority = priority
        self.status = status
        self.validation_result = validation_result or {}
        self.performance_metrics = performance_metrics or {}
        self.impact_metrics = impact_metrics or {}
        self.timestamp = timestamp or datetime.now()
        self.applied_at: Optional[datetime] = None
        self.rollback_count: int = 0
        self.review_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "improvement_id": self.improvement_id,
            "improvement_type": self.improvement_type,
            "file_path": self.file_path,
            "original_code_hash": self.original_code_hash,
            "modified_code_hash": self.modified_code_hash,
            "rationale": self.rationale,
            "priority": self.priority,
            "status": self.status,
            "validation_result": self.validation_result,
            "performance_metrics": self.performance_metrics,
            "impact_metrics": self.impact_metrics,
            "timestamp": self.timestamp.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "rollback_count": self.rollback_count,
            "review_notes": self.review_notes,
        }
    
    def mark_applied(self, validation_result: Dict[str, Any], performance_metrics: Dict[str, Any]):
        """Mark the improvement as applied."""
        self.status = "applied"
        self.applied_at = datetime.now()
        self.validation_result = validation_result
        self.performance_metrics = performance_metrics
    
    def mark_failed(self, error_message: str):
        """Mark the improvement as failed."""
        self.status = "failed"
        self.validation_result["error"] = error_message
    
    def mark_rolled_back(self):
        """Mark the improvement as rolled back."""
        self.status = "rolled_back"
        self.rollback_count += 1


class ImprovementHistory:
    """Tracks and analyzes improvement history for learning and optimization."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.improvements: List[ImprovementRecord] = []
        self.storage_path = storage_path
        self._load_from_storage()
    
    def add_improvement(
        self,
        improvement_id: str,
        improvement_type: str,
        file_path: str,
        original_code_hash: str,
        modified_code_hash: str,
        rationale: str,
        priority: float,
        validation_result: Optional[Dict[str, Any]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
        impact_metrics: Optional[Dict[str, Any]] = None,
    ) -> ImprovementRecord:
        """
        Add a new improvement record.
        
        Args:
            improvement_id: Unique identifier for the improvement
            improvement_type: Type of improvement (e.g., complexity_reduction, performance_improvement)
            file_path: Path to the file being modified
            original_code_hash: Hash of original code
            modified_code_hash: Hash of modified code
            rationale: Rationale for the improvement
            priority: Priority score (0-1)
            validation_result: Validation result from validator
            performance_metrics: Performance metrics from testing
            impact_metrics: Impact metrics (e.g., complexity reduction, performance improvement)
            
        Returns:
            The created ImprovementRecord
        """
        record = ImprovementRecord(
            improvement_id=improvement_id,
            improvement_type=improvement_type,
            file_path=file_path,
            original_code_hash=original_code_hash,
            modified_code_hash=modified_code_hash,
            rationale=rationale,
            priority=priority,
            validation_result=validation_result,
            performance_metrics=performance_metrics,
            impact_metrics=impact_metrics,
        )
        
        self.improvements.append(record)
        self._save_to_storage()
        
        logger.info(
            f"Added improvement {improvement_id}: {improvement_type} on {file_path}"
        )
        
        return record
    
    def record_improvement_outcome(
        self,
        improvement_id: str,
        status: str,
        validation_result: Optional[Dict[str, Any]] = None,
        performance_metrics: Optional[Dict[str, Any]] = None,
    ):
        """
        Record the outcome of an improvement attempt.
        
        Args:
            improvement_id: ID of the improvement
            status: Outcome status (approved, applied, failed, rolled_back)
            validation_result: Validation result
            performance_metrics: Performance metrics
        """
        for record in self.improvements:
            if record.improvement_id == improvement_id:
                if status == "applied":
                    record.mark_applied(validation_result or {}, performance_metrics or {})
                elif status == "failed":
                    record.mark_failed(validation_result.get("error", "Unknown error") if validation_result else "Unknown error")
                elif status == "rolled_back":
                    record.mark_rolled_back()
                else:
                    record.status = status
                
                self._save_to_storage()
                logger.info(f"Recorded outcome for improvement {improvement_id}: {status}")
                break
    
    def get_improvement(self, improvement_id: str) -> Optional[ImprovementRecord]:
        """Get a specific improvement record."""
        for record in self.improvements:
            if record.improvement_id == improvement_id:
                return record
        return None
    
    def get_improvements_by_type(
        self, improvement_type: str
    ) -> List[ImprovementRecord]:
        """Get improvements of a specific type."""
        return [r for r in self.improvements if r.improvement_type == improvement_type]
    
    def get_improvements_by_file(self, file_path: str) -> List[ImprovementRecord]:
        """Get improvements for a specific file."""
        return [r for r in self.improvements if r.file_path == file_path]
    
    def get_improvements_by_status(self, status: str) -> List[ImprovementRecord]:
        """Get improvements with a specific status."""
        return [r for r in self.improvements if r.status == status]
    
    def get_successful_improvements(self) -> List[ImprovementRecord]:
        """Get all successfully applied improvements."""
        return [r for r in self.improvements if r.status == "applied"]
    
    def get_failed_improvements(self) -> List[ImprovementRecord]:
        """Get all failed improvement attempts."""
        return [r for r in self.improvements if r.status == "failed"]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about improvement history.
        
        Returns:
            Dictionary containing various statistics
        """
        total = len(self.improvements)
        if total == 0:
            return {
                "total_improvements": 0,
                "success_rate": 0.0,
                "by_type": {},
                "by_status": {},
                "average_priority": 0.0,
                "most_common_type": None,
            }
        
        successful = len(self.get_successful_improvements())
        failed = len(self.get_failed_improvements())
        
        # Statistics by type
        by_type = {}
        for record in self.improvements:
            if record.improvement_type not in by_type:
                by_type[record.improvement_type] = {"total": 0, "success": 0}
            by_type[record.improvement_type]["total"] += 1
            if record.status == "applied":
                by_type[record.improvement_type]["success"] += 1
        
        # Statistics by status
        by_status = {}
        for record in self.improvements:
            if record.status not in by_status:
                by_status[record.status] = 0
            by_status[record.status] += 1
        
        # Average priority
        avg_priority = sum(r.priority for r in self.improvements) / total
        
        # Most common type
        most_common_type = max(by_type.items(), key=lambda x: x[1]["total"])[0] if by_type else None
        
        return {
            "total_improvements": total,
            "successful_improvements": successful,
            "failed_improvements": failed,
            "success_rate": successful / total,
            "by_type": by_type,
            "by_status": by_status,
            "average_priority": avg_priority,
            "most_common_type": most_common_type,
            "recent_improvements": self.improvements[-10:],
        }
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """
        Get insights for optimizing future improvements.
        
        Returns:
            Dictionary containing learning insights
        """
        stats = self.get_statistics()
        
        insights = {
            "success_rate_by_type": {},
            "common_failure_reasons": [],
            "recommended_improvement_types": [],
            "optimal_priority_range": {},
            "frequently_modified_files": {},
        }
        
        # Success rate by type
        for improvement_type, type_stats in stats.get("by_type", {}).items():
            if type_stats["total"] > 0:
                insights["success_rate_by_type"][improvement_type] = (
                    type_stats["success"] / type_stats["total"]
                )
        
        # Most successful types
        successful_types = [
            (type_name, rate)
            for type_name, rate in insights["success_rate_by_type"].items()
            if rate >= 0.7
        ]
        if successful_types:
            insights["recommended_improvement_types"] = [
                t[0] for t in sorted(successful_types, key=lambda x: x[1], reverse=True)[:3]
            ]
        
        # Most modified files
        file_counts = {}
        for record in self.improvements:
            file_counts[record.file_path] = file_counts.get(record.file_path, 0) + 1
        insights["frequently_modified_files"] = dict(
            sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        )
        
        # Optimal priority range based on success rates
        if stats["total_improvements"] > 10:
            successful_priorities = [
                r.priority for r in self.improvements if r.status == "applied"
            ]
            if successful_priorities:
                insights["optimal_priority_range"] = {
                    "min": min(successful_priorities),
                    "max": max(successful_priorities),
                    "average": sum(successful_priorities) / len(successful_priorities),
                }
        
        return insights
    
    def get_trigger_recommendations(self) -> Dict[str, Any]:
        """
        Get recommendations for adaptive trigger thresholds.
        
        Returns:
            Dictionary with trigger threshold recommendations
        """
        insights = self.get_learning_insights()
        stats = self.get_statistics()
        
        recommendations = {
            "base_threshold": 0.5,
            "adjustment_factors": {},
            "recommended_actions": [],
        }
        
        # Adjust base threshold based on success rate
        success_rate = stats.get("success_rate", 1.0)
        if success_rate < 0.5:
            recommendations["base_threshold"] = 0.6  # Require higher threshold if failures are common
            recommendations["recommended_actions"].append(
                "Increase threshold to reduce failed improvements"
            )
        elif success_rate > 0.8:
            recommendations["base_threshold"] = 0.4  # Allow more improvements if successful
            recommendations["recommended_actions"].append(
                "Lower threshold to enable more improvements"
            )
        
        # Adjust based on improvement type success rates
        for improvement_type, success_rate in insights.get("success_rate_by_type", {}).items():
            if success_rate < 0.5:
                recommendations["adjustment_factors"][improvement_type] = 1.2  # Require higher threshold
                recommendations["recommended_actions"].append(
                    f"Increase threshold for {improvement_type} improvements"
                )
            elif success_rate > 0.8:
                recommendations["adjustment_factors"][improvement_type] = 0.8  # Allow lower threshold
                recommendations["recommended_actions"].append(
                    f"Lower threshold for {improvement_type} improvements"
                )
        
        return recommendations
    
    def get_performance_trends(self) -> Dict[str, Any]:
        """
        Analyze performance trends over time.
        
        Returns:
            Dictionary with performance trend analysis
        """
        improvements_by_date = {}
        
        for record in self.improvements:
            date = record.timestamp.date().isoformat()
            if date not in improvements_by_date:
                improvements_by_date[date] = []
            improvements_by_date[date].append(record)
        
        trends = {
            "daily_improvement_counts": {},
            "success_rates_by_date": {},
            "trend": "stable",
        }
        
        for date, records in improvements_by_date.items():
            trends["daily_improvement_counts"][date] = len(records)
            successful = len([r for r in records if r.status == "applied"])
            trends["success_rates_by_date"][date] = (
                successful / len(records) if records else 0
            )
        
        # Determine trend
        if len(trends["success_rates_by_date"]) >= 3:
            recent_rates = list(trends["success_rates_by_date"].values())[-3:]
            if all(r > 0.6 for r in recent_rates):
                trends["trend"] = "improving"
            elif any(r < 0.4 for r in recent_rates):
                trends["trend"] = "degrading"
        
        return trends
    
    def _save_to_storage(self):
        """Save improvements to storage file."""
        if not self.storage_path:
            return
        
        try:
            storage_dir = Path(self.storage_path).parent
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            data = {
                "improvements": [r.to_dict() for r in self.improvements],
                "last_updated": datetime.now().isoformat(),
            }
            
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save improvement history: {e}")
    
    def _load_from_storage(self):
        """Load improvements from storage file."""
        if not self.storage_path or not Path(self.storage_path).exists():
            return
        
        try:
            with open(self.storage_path, "r") as f:
                data = json.load(f)
            
            self.improvements = [
                ImprovementRecord(**record)
                for record in data.get("improvements", [])
            ]
            
            logger.info(f"Loaded {len(self.improvements)} improvements from storage")
            
        except Exception as e:
            logger.error(f"Failed to load improvement history: {e}")
    
    def reset(self):
        """Reset all improvement history."""
        self.improvements.clear()
        self._save_to_storage()
        logger.info("Improvement history reset")
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export all improvements to a dictionary."""
        return {
            "statistics": self.get_statistics(),
            "learning_insights": self.get_learning_insights(),
            "trigger_recommendations": self.get_trigger_recommendations(),
            "performance_trends": self.get_performance_trends(),
            "improvements": [r.to_dict() for r in self.improvements],
        }
    
    def export_to_json(self, file_path: str):
        """Export improvements to a JSON file."""
        try:
            export_data = self.export_to_dict()
            
            storage_dir = Path(file_path).parent
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "w") as f:
                json.dump(export_data, f, indent=2)
                
            logger.info(f"Exported improvement history to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to export improvement history: {e}")
