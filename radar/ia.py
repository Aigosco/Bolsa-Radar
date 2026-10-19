"""Cliente común de IA (Claude) para el sistema de noticias: devuelve SIEMPRE JSON validado por un esquema.

Credenciales: variable de entorno ANTHROPIC_API_KEY (o un perfil de `ant auth login`). Sin credenciales, `disponible()`
devuelve False y los módulos que lo usan dejan su parte "pendiente" en vez de fallar (nada se inventa).
Modelo: Claude Opus 5.5 con `fallbacks: "default"`: si un clasificador de seguridad rechaza la petición, la API la
reintenta sola con el modelo de respaldo recomendado.
"""
import json
import os

MODELO = "claude-opus-5-5"


def disponible():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.environ.get("ANTHROPIC_PROFILE")
                or os.path.exists(os.path.expanduser("~/.config/anthropic")))


def pedir_json(sistema, texto, esquema, esfuerzo="high", max_tokens=32000):
    """Una llamada con salida estructurada (output_config.format). Devuelve (dict, info) o lanza RuntimeError."""
    import anthropic
    # Una clave que no pertenece a un workspace exige indicar cuál usar (secreto opcional ANTHROPIC_WORKSPACE_ID)
    ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    cliente = anthropic.Anthropic(default_headers={"anthropic-workspace-id": ws} if ws else None)
    try:
        with cliente.beta.messages.stream(
            model=MODELO,
            max_tokens=max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=sistema,
            output_config={"effort": esfuerzo, "format": {"type": "json_schema", "schema": esquema}},
            messages=[{"role": "user", "content": texto}],
        ) as stream:
            r = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise RuntimeError("clave de API inválida") from e
    except anthropic.RateLimitError as e:
        raise RuntimeError("límite de uso de la API alcanzado; reintentar más tarde") from e
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"error de la API {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise RuntimeError("sin conexión con la API") from e
    if r.stop_reason == "refusal":
        cat = getattr(r.stop_details, "category", None) if r.stop_details else None
        raise RuntimeError(f"la petición fue rechazada (categoría {cat})")
    if r.stop_reason == "max_tokens":
        raise RuntimeError("respuesta cortada por max_tokens")
    txt = next(b.text for b in r.content if b.type == "text")
    info = {"modelo": r.model, "entrada": r.usage.input_tokens, "salida": r.usage.output_tokens,
            "request_id": r._request_id}
    return json.loads(txt), info
