
import re
import datetime as dt
from copy import deepcopy
NOW = dt.datetime(2026, 10, 19, 10, 0)
def interpret_reply(text):
    if not isinstance(text, str) or not text.strip():
        return 'unclear'

    # 1. Normalize the input
    normalized = text.strip().lower()
    normalized = re.sub(r'[.!]+$', '', normalized).strip()

    # 2. Define clear, unconditional replies
    yes_replies = {
        "yes", "y", "sure", "آره", "آری", "بله", "بلی", "ok", "yes, please", "yes please", "okay thanks",
        "okay", "go ahead", "that works", "sounds good", "perfect", "yes please do", "absolutely"
    }

    no_replies = {
        "no", "n", "never", "نه", "خیر", "نخیر", "no, thanks", "no thanks",
        "nope", "nah", "not yet", "stop", "no thanks", "don't book it", "never mind"
    }

    # 3. Classify the reply
    if normalized in yes_replies:
        return 'yes'
    if normalized in no_replies:
        return 'no'

    return 'unclear'

def cancellation_fee_cents(price_cents, start, now):
    # 1. Reject a booking that has already started
    if start <= now:
        raise ValueError("Booking has already started")

    # 2. Calculate remaining time
    remaining = (start - now).total_seconds() / 3600

    # 3. Apply cancellation policy
    if remaining >= 24:
        return 0
    elif remaining >= 2:
        return price_cents // 2
    else:
        return price_cents

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "List all salon services and their prices.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_slots",
            "description": "Find available appointment slots for a service on a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "ID of the service the client wants to book.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date the client wants to book, preferably in YYYY-MM-DD format.",
                    },
                    "stylist_id": {
                        "type": "string",
                        "description": "Optional ID of the preferred stylist.",
                    },
                },
                "required": ["service_id", "date"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_bookings",
            "description": "List all appointments belonging to the current client.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment with a stylist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": "Appointment start datetime in ISO 8601 format.",
                    },
                    "stylist_id": {
                        "type": "string",
                        "description": "ID of the selected stylist.",
                    },
                    "service_id": {
                        "type": "string",
                        "description": "ID of the selected service.",
                    },
                },
                "required": ["start", "stylist_id", "service_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new start time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "ID of the existing appointment to reschedule.",
                    },
                    "new_start": {
                        "type": "string",
                        "description": "New appointment start datetime in ISO 8601 format.",
                    },
                },
                "required": ["appointment_id", "new_start"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "ID of the existing appointment to cancel."
                    },
                },
                "required": ["appointment_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "handoff_to_human",
            "description": "Conversation with human.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Escalate the customer's issue to a human support agent."
                    },
                },
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    },
]

REQUIRE_CONFORMATION = {
    "book_appointment",
    "reschedule_appointment",
    "cancel_appointment"
}

import json
import re
from copy import deepcopy


class SalonAssistant:
    def __init__(self, model, backend, clock):
        self.model = model
        self.backend = backend
        self.clock = clock
        self.sessions = {}
        self.audit = []

    def open_session(self, session_id, customer_id):
        if session_id in self.sessions:
            return False

        self.sessions[session_id] = {
            "customer_id": customer_id,
            "messages": [],
            "pending": None,
            "turn": 0,
        }
        return True

    def _add_message(self, session, role, content):
        session["messages"].append({
            "role": role,
            "content": content,
        })

    def _add_audit(
        self,
        session_id,
        session_turn,
        call_id,
        tool,
        status,
        error_type,
        attempts,
        preview,
    ):
        event = {
            "session": session_id,
            "turn": session_turn,
            "call_id": call_id,
            "tool": tool,
            "status": status,
            "error_type": error_type,
            "attempts": attempts,
            "preview": preview,
        }
        self.audit.append(event)
        return event

    def _safe_preview(self, text, max_len=80):
        # Redact common email and phone patterns.
        result = re.sub(
            r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
            "[EMAIL]",
            str(text),
        )
        result = re.sub(
            r"\+?\d[\d\s().-]{7,}\d",
            "[PHONE]",
            result,
        )
        return result[:max_len]

    def _build_system_prompt(self):
        now = self.clock()
        formatted_time = now.strftime("%Y-%m-%d %H:%M (%A)")

        return (
            f"Now: {formatted_time}\n"
            "1. Role: You are a salon booking assistant.\n"
            "2. Use tools to retrieve salon information. Never invent "
            "services, prices, appointment times, or booking IDs.\n"
            "3. Booking, rescheduling, and cancellation require explicit "
            "customer confirmation before execution."
        )

    def _validate_tool_call(self, response):
        if not isinstance(response, dict):
            return None

        tool_calls = response.get("tool_calls")
        if tool_calls:
            if not isinstance(tool_calls, list):
                return None
            return "TOOL_CALL_DETECTED"

        if isinstance(response.get("final"), str):
            return response["final"]

        return None

    def _parse_tool_arguments(self, arguments):
        if isinstance(arguments, dict):
            return arguments

        if not isinstance(arguments, str):
            return None

        try:
            parsed = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            return None

        return parsed if isinstance(parsed, dict) else None

    def _validate_types(self, tool_name, arguments):
        tool_keys = KEY_TYPES.get(tool_name)
        if tool_keys is None:
            return False

        for key, value in arguments.items():
            expected_type = tool_keys.get(key)

            if expected_type is None:
                return False

            # bool is a subclass of int, so reject it for integer fields.
            if expected_type is int:
                if type(value) is not int:
                    return False
            elif not isinstance(value, expected_type):
                return False

        return True

    def _validate_tool_keys(self, tool_name, arguments):
        if (
            tool_name not in REQUIRED_KEYS
            or tool_name not in ALLOWED_KEYS
            or tool_name not in KEY_TYPES
        ):
            return False

        args = self._parse_tool_arguments(arguments)
        if args is None:
            return False

        required_keys = set(REQUIRED_KEYS[tool_name])
        allowed_keys = set(ALLOWED_KEYS[tool_name])
        actual_keys = set(args)

        missing = required_keys - actual_keys
        extra = actual_keys - allowed_keys

        if missing or extra:
            return False

        return self._validate_types(tool_name, args)

    def _extract_tool_call(self, raw_call):
        """Normalize common OpenAI-style and simplified tool-call formats."""
        if not isinstance(raw_call, dict):
            return None

        function = raw_call.get("function", raw_call)

        if not isinstance(function, dict):
            return None

        tool_name = function.get("name")
        arguments = function.get("arguments")

        if not isinstance(tool_name, str) or not tool_name:
            return None

        parsed_args = self._parse_tool_arguments(arguments)
        if parsed_args is None:
            return None

        return {
            "call_id": raw_call.get("id"),
            "tool": tool_name,
            "arguments": parsed_args,
        }

    def _requires_confirmation(self, tool_name):
        return tool_name in REQUIRE_CONFORMATION

    def handle(self, session_id, user_text):
        session = self.sessions.get(session_id)

        if session is None:
            return {"status": "unknown_session"}

        if not isinstance(user_text, str) or not user_text.strip():
            return {"status": "parse_error"}

        user_text = user_text.strip()

        # Do not accept another request while an action is pending.
        if session["pending"] is not None:
            return {"status": "pending_action"}

        session["turn"] += 1
        turn = session["turn"]

        self._add_message(session, "user", user_text)

        self._add_audit(
            session_id=session_id,
            session_turn=turn,
            call_id=None,
            tool="(user)",
            status="received",
            error_type=None,
            attempts=0,
            preview=self._safe_preview(user_text),
        )

        messages = deepcopy(session["messages"])
        messages.insert(0, {
            "role": "system",
            "content": self._build_system_prompt(),
        })

        try:
            model_response = self.model(messages, TOOL_SCHEMAS)
        except Exception:
            self._add_audit(
                session_id, turn, None, "(model)",
                "error", "model_error", 1, "",
            )
            return {"status": "model_error"}

        response_type = self._validate_tool_call(model_response)

        if response_type is None:
            self._add_audit(
                session_id, turn, None, "(model)",
                "error", "invalid_model_response", 1, "",
            )
            return {"status": "invalid_model_response"}

        if response_type != "TOOL_CALL_DETECTED":
            self._add_message(session, "assistant", response_type)
            return {
                "status": "final",
                "message": response_type,
            }

        tool_calls = model_response["tool_calls"]

        # This implementation deliberately supports one call per turn.
        if len(tool_calls) != 1:
            return {"status": "unsupported_tool_call_count"}

        call = self._extract_tool_call(tool_calls[0])

        if call is None:
            self._add_audit(
                session_id, turn, None, "(unknown)",
                "rejected", "invalid_tool_call", 0, "",
            )
            return {"status": "invalid_tool_call"}

        tool_name = call["tool"]
        arguments = call["arguments"]
        call_id = call["call_id"]

        if not self._validate_tool_keys(tool_name, arguments):
            self._add_audit(
                session_id, turn, call_id, tool_name,
                "rejected", "invalid_arguments", 0,
                self._safe_preview(json.dumps(arguments)),
            )
            return {"status": "invalid_tool_arguments"}

        # Store a validated proposal. Do not execute it here.
        # The controller must determine whether confirmation is required
        # and whether the customer has explicitly approved the action.
        session["pending"] = {
            "call_id": call_id,
            "tool": tool_name,
            "arguments": arguments,
            "turn": turn,
        }

        self._add_audit(
            session_id, turn, call_id, tool_name,
            "validated_pending", None, 0,
            self._safe_preview(json.dumps(arguments)),
        )

        return {
            "status": "validated_pending",
            "tool": tool_name,
            "arguments": arguments,
            "call_id": call_id,
        }


def mock_invalid_tool(messages, tools=None):
    return {
        "tool_calls": [{
            "id": "call_001",
            "name": "find_slots",
            "arguments": '{"service_id": 123, "date": "2026-10-20"}'
        }]
    }

assistant = SalonAssistant(
    model=None,
    backend=None,
    clock=lambda: NOW
)

assistant.open_session("s1", "c101")

pending_action = {
    "call_id": "call_001",
    "tool": "book_appointment",
    "arguments": {
        "service_id": "S1",
        "stylist_id": "ST1",
        "start": "2026-10-23 11:00"
    },
    "turn": 1
}

# Test confirmation
assistant.sessions["s1"]["pending"] = pending_action.copy()

result = assistant.handle("s1", "yes")

assert result["status"] == "confirmed"
assert assistant.sessions["s1"]["pending"] is not None

# Test rejection
result = assistant.handle("s1", "no")

assert result["status"] == "cancelled"
assert assistant.sessions["s1"]["pending"] is None

# Test ambiguous response
assistant.sessions["s1"]["pending"] = pending_action.copy()

result = assistant.handle("s1", "maybe")

assert result["status"] == "awaiting_confirmation"
assert assistant.sessions["s1"]["pending"] is not None

print("Pending confirmation handling passed")




