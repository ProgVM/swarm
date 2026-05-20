from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None

    def __str__(self):
        return str(self.data) if self.success else f"Error: {self.error}"
