from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

@dataclass
class FaceData:
    """Represents a single face image file."""
    path: Path
    filename: str = field(init=False)

    def __post_init__(self):
        self.filename = self.path.name

@dataclass
class PersonData:
    """Represents a person with their associated face images."""
    name: str
    directory_path: Path
    faces: List[FaceData] = field(default_factory=list)

@dataclass
class SourceImageData:
    """Represents a single source image file."""
    path: Path
    filename: str = field(init=False)

    def __post_init__(self):
        self.filename = self.path.name

@dataclass
class SwapTaskData:
    """Represents a single face swap task to be performed."""
    person: PersonData
    face: FaceData
    source_image: SourceImageData
    output_dir: Path # Where to save the temp result
    # Optional: Add status field later if needed (e.g., pending, running, done, error) 