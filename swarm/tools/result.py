from dataclasses import dataclass, field
from typing import Any, Optional, List

@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    extra_parts: List[Any] = field(default_factory=list)

    def __str__(self):
        return str(self.data) if self.success else f"Error: {self.error}"
