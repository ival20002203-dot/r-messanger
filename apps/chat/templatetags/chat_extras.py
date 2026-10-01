from django import template
register=template.Library()
@register.filter
def split(value,sep=" "):
    return str(value).split(sep)


@register.filter
def receipt_mark(message):
    rows=list(message.receipts.all())
    return "✓✓" if rows and all(row.read_at for row in rows) else "✓"
