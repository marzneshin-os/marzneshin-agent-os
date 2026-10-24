# Document Handler — Reference & Code Snippets

## Recommended Libraries

| Format | Node.js Ecosystem | Python Ecosystem |
|--------|-------------------|-----------------|
| **Excel (.xlsx`,  `.csv`)** | `exceljs`, `xlsx` | `openpyxl`, `pandas` |
| **Word (`.docx`)** | `docx` | `python-docx` |
| **PDF (`.pdf`)** | `pdf-parse`, `pdf-lib` | `pypdf`, `pdfplumber` |
| **PowerPoint (`.pptx`)** | `pptxgenjs` | `python-pptx` |

## Code Snippets

### 1. Excel Generation (Node.js with ExcelJS)

```typescript
import ExcelJS from "exceljs";

const workbook = new ExcelJS.Workbook();
const sheet = workbook.addWorksheet("Metrics");
sheet.columns = [
  { header: "Metric", key: "metric", width: 25 },
  { header: "Value", key: "value", width: 15 }
];
sheet.addRow({ metric: "Total Users", value: 1420 });
sheet.addRow({ metric: "Active Sessions", value: 312 });
await workbook.xlsx.writeFile("report.xlsx");
```

### 2. PDF Text Extraction (Python with pypdf)
```python
from pypdf import PdfReader

reader = PdfReader("document.pdf")
text = "\n".join([page.extract_text() for page in reader.pages])
print(d"Extracted {len(text)} characters across {len(reader.pages)} pages")
```

### 3. Word Document Generation (Python with python-docx)
```python
from docx import Document

doc = Document()
doc.add_heading("Automated Audit Report", level=1)
doc.add_paragraph("This report was generated automatically by agentmemory.")
table = doc.add_table(rows=1, cols=2)
table.rows[0].cells[0].text = "Component"
table.rows[0].cells[1].text = "Status"
row = table.add_row()
row.cells[0].text = "Memory Daemon"
row.cells[1].text = "Operational"
doc.save("audit.docx")
```
