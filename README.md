# Equipment Decommissioning

> **Professional desktop application for equipment decommissioning, asset identification, technical documentation and automated printing.**

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge\&logo=python\&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge\&logo=postgresql\&logoColor=white)](https://www.postgresql.org/)
[![OpenDocument](https://img.shields.io/badge/OpenDocument-ODT-0A66C2?style=for-the-badge)](https://www.oasis-open.org/standards/)
[![Excel](https://img.shields.io/badge/Excel-XLS-217346?style=for-the-badge\&logo=microsoftexcel\&logoColor=white)](https://www.microsoft.com/microsoft-365/excel)
[![Git](https://img.shields.io/badge/Git-Version_Control-F05032?style=for-the-badge\&logo=git\&logoColor=white)](https://git-scm.com/)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge\&logo=github\&logoColor=white)](https://github.com/Drwalpawel20/Equipment-Decommissioning)

### 🛠️ Technology Stack

| Category                | Technology / Library           | Purpose                                               |
| ----------------------- | ------------------------------ | ----------------------------------------------------- |
| **Language**            | Python                         | Core application logic and automation                 |
| **Database**            | PostgreSQL                     | Equipment and technical data storage                  |
| **Database Access**     | PostgreSQL Driver              | Communication between Python and PostgreSQL           |
| **GUI**                 | Python Desktop GUI             | User interface and application workflow               |
| **Documents**           | ODT / OpenDocument             | Technical document templates and generated reports    |
| **Document Processing** | ODT Processing Libraries       | Automatic template population and document generation |
| **Data Processing**     | XLS / Excel                    | Equipment and passport data processing                |
| **Scanner Integration** | Barcode / Label Reader         | Fast equipment identification                         |
| **Printing**            | Python Print Service           | Direct printing of generated documents                |
| **Configuration**       | `.env` / Environment Variables | Secure database configuration                         |
| **Version Control**     | Git                            | Source code version control                           |
| **Repository**          | GitHub                         | Project hosting and development                       |

---

## 🚀 Core Technologies

### 🐍 Python

Python is the core technology behind the application.

It is responsible for:

* application logic
* database communication
* equipment identification
* document generation
* template processing
* printing
* automation of the decommissioning workflow

### 🗄️ PostgreSQL

PostgreSQL is used as the main relational database for storing equipment and technical information.

The application retrieves equipment data directly from the database, allowing the operator to avoid unnecessary manual data entry.

### 📄 OpenDocument / ODT

The application uses **ODT templates** for generating technical documentation.

Dynamic fields can be automatically populated using equipment information retrieved from the database.

### 🏷️ Barcode / Label Scanner

The system supports external label readers and barcode scanners.

This allows the operator to identify equipment by scanning its label instead of manually entering identification numbers.

### 🖨️ Printing Integration

Generated documentation can be sent directly to a configured printer.

This creates an end-to-end workflow:

**Scan → Retrieve → Verify → Generate → Print**

### 📊 Excel / XLS

The project supports spreadsheet-based equipment data and technical passport information.

### 🔐 Environment Configuration

Database credentials are stored outside the source code using environment variables.

Example:

```env
DB_HOST=your_host
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_username
DB_PASSWORD=your_password
```

Sensitive configuration is excluded from Git using `.gitignore`.

---

## 🧩 Main Python Modules

| Module                | Description                               |
| --------------------- | ----------------------------------------- |
| `database.py`         | Database communication and data retrieval |
| `disposal_objects.py` | Equipment/decommissioning data structures |
| `generator.py`        | Document generation                       |
| `gui_generator.py`    | Main GUI and generation workflow          |
| `skaner.py`           | Scanner / label reader integration        |
| `print_service.py`    | Direct printing functionality             |
| `odt_editor.py`       | ODT document processing                   |
| `rich_odt_editor.py`  | Advanced ODT editing                      |
| `template_editor.py`  | Template editing and management           |

The repository currently contains these dedicated modules alongside the document templates, XLS data and application screenshots.

---

## 🔄 End-to-End Workflow

```text
┌───────────────────────┐
│   Barcode / Label     │
│       Scanner         │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│       PostgreSQL      │
│      Equipment DB     │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│    Equipment Data     │
│      Validation       │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│   Document Generator  │
│    + ODT Templates    │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│    Generated Report   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│    Direct Printing    │
└───────────────────────┘
```

### Result

The application transforms a traditionally manual process into a single digital workflow:

> **Identify → Retrieve → Verify → Generate → Print**

---

## 📦 Architecture

The project follows a modular Python architecture where individual components are responsible for separate parts of the workflow:

```text
                    Equipment Decommissioning
                              │
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
        User Interface    Database Layer   Hardware I/O
             │                │                │
             │                ▼                ▼
             │            PostgreSQL       Scanner
             │
             ▼
       Business Logic
             │
      ┌──────┴──────┐
      ▼             ▼
 Document         Template
 Generator        Processing
      │             │
      └──────┬──────┘
             ▼
          Printing
```
