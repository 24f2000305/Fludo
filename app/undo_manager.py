"""Undo/Redo manager for CAD Studio code history."""
from __future__ import annotations

from typing import List, Optional, Dict
from datetime import datetime


class CodeHistoryEntry:
    """Single entry in the code history."""
    
    def __init__(self, code: str, description: str = ""):
        self.code = code
        self.description = description
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "description": self.description,
            "timestamp": self.timestamp.isoformat()
        }


class UndoRedoManager:
    """
    Manages undo/redo history for code changes.
    Stores a stack of code states with descriptions.
    """
    
    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.history: List[CodeHistoryEntry] = []
        self.current_index: int = -1
    
    def push(self, code: str, description: str = ""):
        """
        Add new code state to history.
        Clears any redo history after current position.
        """
        # Remove any history after current index (redo gets cleared)
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        # Add new entry
        entry = CodeHistoryEntry(code, description)
        self.history.append(entry)
        
        # Limit history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
        else:
            self.current_index += 1
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self.current_index > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self.current_index < len(self.history) - 1
    
    def undo(self) -> Optional[CodeHistoryEntry]:
        """
        Undo to previous state.
        Returns the previous code entry, or None if can't undo.
        """
        if not self.can_undo():
            return None
        
        self.current_index -= 1
        return self.history[self.current_index]
    
    def redo(self) -> Optional[CodeHistoryEntry]:
        """
        Redo to next state.
        Returns the next code entry, or None if can't redo.
        """
        if not self.can_redo():
            return None
        
        self.current_index += 1
        return self.history[self.current_index]
    
    def get_current(self) -> Optional[CodeHistoryEntry]:
        """Get current code state."""
        if self.current_index < 0 or self.current_index >= len(self.history):
            return None
        return self.history[self.current_index]
    
    def get_history_list(self, limit: int = 20) -> List[Dict]:
        """
        Get list of history entries for display.
        Returns most recent entries up to limit.
        """
        start_idx = max(0, len(self.history) - limit)
        return [
            {
                **entry.to_dict(),
                "index": i,
                "is_current": i == self.current_index
            }
            for i, entry in enumerate(self.history[start_idx:], start=start_idx)
        ]
    
    def clear(self):
        """Clear all history."""
        self.history = []
        self.current_index = -1
    
    def jump_to(self, index: int) -> Optional[CodeHistoryEntry]:
        """
        Jump to specific history index.
        Returns the entry at that index, or None if invalid.
        """
        if index < 0 or index >= len(self.history):
            return None
        
        self.current_index = index
        return self.history[self.current_index]


# Global history managers for each session
# In production, this should be per-session/per-user
_session_managers: Dict[str, UndoRedoManager] = {}


def get_manager(session_id: str = "default") -> UndoRedoManager:
    """Get or create undo/redo manager for a session."""
    if session_id not in _session_managers:
        _session_managers[session_id] = UndoRedoManager()
    return _session_managers[session_id]


def clear_session(session_id: str):
    """Clear history for a session."""
    if session_id in _session_managers:
        del _session_managers[session_id]
