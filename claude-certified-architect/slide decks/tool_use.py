# The tool doesn't need to do anything real.
# Its job is to enforce schema compliance on the output.

tools = [
    {
        "name": "extract_invoice_data",
        "description": "Extract structured invoice information from the document",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor_name": {
                    "type": "string",
                    "description": "The name of the vendor or supplier"
                },
                "total_amount": {
                    "type": "number",
                    "description": "Total invoice amount in USD"
                },
                "invoice_date": {
                    "type": "string",
                    "description": "Invoice date in YYYY-MM-DD format"
                }
            },
            "required": ["vendor_name", "total_amount", "invoice_date"]
        }
    }
]

response = client.messages.create(
    model="claude-opus-4-5-20251001",
    max_tokens=1024,
    tools=tools,
    # We haven't set tool_choice yet — more on that in a moment
    messages=[{"role": "user", "content": f"Extract invoice data from: {document}"}]



{
    "type": "object",
    "properties": {
        "vendor_name": {
            "type": "string",
            "description": "Vendor name as it appears on the invoice header"
        },
        "purchase_order": {
            "type": ["string", "null"],   ← nullable type
            "description": "PO number if present, null if not found"
        },
        "payment_terms": {
            "type": ["string", "null"],   ← nullable type
            "description": "Payment terms (e.g. Net 30), null if not stated"
        }
    },
    "required": ["vendor_name", "purchase_order", "payment_terms"]
    ^ All fields required — but nullable types prevent fabrication
}

// ❌ APPROACH 1: Required, non-nullable — FORCES fabrication
"tax_id": {
    "type": "string"   ← if absent from doc, model invents a plausible tax ID
}
"required": ["tax_id"]

// ⚠️ APPROACH 2: Optional only — may be omitted entirely
"tax_id": {
    "type": "string"
}
// NOT in required array — model may skip it completely

// ✅ APPROACH 3: Required + nullable — honest null when absent
"tax_id": {
    "type": ["string", "null"],  ← explicitly nullable
    "description": "Tax ID number, or null if not present in document"
}
"required": ["tax_id"]  ← must appear, but null is valid


def extract_with_retry(document, max_retries=2):
    messages = [{"role": "user", "content": f"Extract data: {document}"}]

    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model="claude-opus-4-5-20251001",
            tools=tools,
            tool_choice={"type": "any"},
            messages=messages
        )

        result = response.content[0].input
        errors = validate_extraction(result)  # your validation logic

        if not errors:
            return result  # ✅ clean extraction

        # Append assistant response to history
        messages.append({"role": "assistant", "content": response.content})

        # Append specific error as tool result — BE PRECISE
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": response.content[0].id,
                "content": f"Validation failed: {'; '.join(errors)}"
                # e.g. "invoice_date must be YYYY-MM-DD, got '01/15/2024'"
                # NOT "Extraction failed. Try again."
            }]
        })

    raise ValueError(f"Extraction failed after {max_retries} retries")




