from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class ReaderDirectionEnum(str, Enum):
    IN_ONLY = "IN_ONLY"
    IN_OUT = "IN_OUT"
    NONE = "NONE"


class LockTypeEnum(str, Enum):
    ELECTRIC_LOCK = "ELECTRIC_LOCK"
    ELECTRIC_STRIKE_PLATE = "ELECTRIC_STRIKE_PLATE"
    MAGNETIC_LOCK = "MAGNETIC_LOCK"
    MOTORIZED_LOCK = "MOTORIZED_LOCK"
    ELECTRIC_DOOR_CLOSER = "ELECTRIC_DOOR_CLOSER"


class ReaderTypeEnum(str, Enum):
    CARD = "CARD"
    CODE = "CODE"
    FINGERPRINT = "FINGERPRINT"
    FACE_RECOGNITION = "FACE_RECOGNITION"
    IRIS_SCAN = "IRIS_SCAN"
    BLUETOOTH = "BLUETOOTH"
    NFC = "NFC"
    OTHER = "OTHER"


class DoorRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    areas: List[str]
    reader_direction: Optional[ReaderDirectionEnum] = None
    lock_type: Optional[LockTypeEnum] = None

    door_sensor: Optional[bool] = None
    exit_button: Optional[bool] = None
    emergency_button: Optional[bool] = None
    door_closer: Optional[bool] = None
    anti_passback: Optional[bool] = None

    reader_types: List[ReaderTypeEnum] = Field(default_factory=list)
    description: Optional[str] = None


class ControllerRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    areas: List[str] = Field(default_factory=list)
    door_count: int = Field(ge=1, le=99)
    description: Optional[str] = None


class AccessControlExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    door_rules: List[DoorRule] = Field(default_factory=list)
    controller_rules: List[ControllerRule] = Field(default_factory=list)