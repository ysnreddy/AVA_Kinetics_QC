# AVA_Kinetics_QC Documentation

Welcome to the comprehensive documentation for the AVA_Kinetics_QC Quality Control system. This directory contains detailed technical documentation, architecture diagrams, and workflow visualizations for the entire system.

## 📚 Documentation Contents

### 1. [Technical-Documentation.md](Technical-Documentation.md)
**Complete Technical Reference** - ~15,000+ words

#### Contents:
- **Executive Summary** - Project overview and core capabilities
- **System Overview** - High-level architecture and technology stack
- **Module Documentation** - Detailed documentation for all components:
  - Proposal Generation Pipeline (15+ modules)
  - Processing Pipeline (10+ service modules)
  - Quality Control System (rule engine, routing, validation)
  - Metrics Logging (event tracking and analytics)
  - Deployment Configuration (FastAPI, Docker, AWS)
- **Database Architecture** - Complete PostgreSQL schema
- **API Reference** - All RESTful endpoints with examples
- **Configuration Management** - Environment variables and settings
- **Integration Points** - CVAT, AWS S3, PostgreSQL integrations
- **Workflow Documentation** - Complete annotation workflow
- **Installation Guide** - Step-by-step setup instructions
- **Troubleshooting** - Common issues and solutions

#### Key Sections:
- 50+ Python modules documented
- 10+ API endpoints
- 4 database tables with JSONB support
- 8 action attribute categories with 58 total labels

---

### 2. [Architecture-Diagrams.md](Architecture-Diagrams.md)
**Visual System Architecture** - 9 comprehensive diagram categories

#### Diagram Categories:
1. **System Architecture Overview**
   - High-level system architecture
   - Microservices architecture
   - Layered architecture view

2. **Component Architecture**
   - Service interaction diagram (Mermaid)
   - Service dependency matrix
   - Module relationships

3. **Data Flow Architecture**
   - End-to-end data flow
   - Data transformation pipeline
   - Format conversions

4. **Deployment Architecture**
   - Docker container architecture
   - AWS cloud deployment
   - Resource allocations

5. **Database Schema**
   - Entity Relationship Diagram (ERD)
   - Table structures
   - Indexes and relationships

6. **Service Interaction Diagram**
   - Complete request/response flows
   - Service communication patterns

7. **Quality Control Pipeline**
   - Validation stages
   - Decision flow
   - Metrics calculation

8. **Network Architecture**
   - Network topology
   - Security groups
   - Port configurations

9. **Module Dependency Graph**
   - Import relationships
   - Layer separation
   - External dependencies

---

### 3. [Flowcharts-Sequences.md](Flowcharts-Sequences.md)
**Process Flows and Interactions** - 14 detailed diagrams

#### Flow Charts (6):
1. **Proposal Generation Pipeline Flow**
   - 7-stage video processing
   - Keyframe selection logic
   - Person detection and tracking

2. **Task Creation Flow**
   - CVAT project setup
   - Label configuration
   - Annotator assignment

3. **Annotation Workflow**
   - Annotator interaction
   - Attribute selection
   - Validation checks

4. **Quality Control Pipeline Flow**
   - Multi-stage validation
   - IoU and Kappa calculation
   - Approval/rejection logic

5. **Dataset Generation Flow**
   - Consensus application
   - AVA format conversion
   - S3 upload process

6. **Rule Engine Validation Flow**
   - Rule processing order
   - Validation logic
   - Action determination

#### Sequence Diagrams (8):
1. **Complete End-to-End Workflow**
2. **Pre-Annotation Processing**
3. **Multi-Annotator Assignment**
4. **Post-Annotation Retrieval**
5. **Quality Metrics Calculation**
6. **Consensus Generation**
7. **S3 Integration Workflow**
8. **Error Recovery Flow**

---

## 🎯 Quick Navigation Guide

### For Different Roles

#### **For Developers**
1. Start with [Technical-Documentation.md](Technical-Documentation.md) - Module Documentation section
2. Review [Architecture-Diagrams.md](Architecture-Diagrams.md) - Component Architecture
3. Study [Flowcharts-Sequences.md](Flowcharts-Sequences.md) - Service interactions

#### **For System Administrators**
1. Review [Architecture-Diagrams.md](Architecture-Diagrams.md) - Deployment Architecture
2. Check [Technical-Documentation.md](Technical-Documentation.md) - Installation Guide
3. Reference Configuration Management section for environment setup

#### **For Project Managers**
1. Read Executive Summary in [Technical-Documentation.md](Technical-Documentation.md)
2. Review System Architecture Overview in [Architecture-Diagrams.md](Architecture-Diagrams.md)
3. Understand workflows in [Flowcharts-Sequences.md](Flowcharts-Sequences.md)

#### **For QA Engineers**
1. Study Quality Control Pipeline in [Flowcharts-Sequences.md](Flowcharts-Sequences.md)
2. Review Rule Engine documentation in [Technical-Documentation.md](Technical-Documentation.md)
3. Check Quality Metrics Calculation sequence diagram

#### **For Data Scientists**
1. Review Dataset Generation Flow in [Flowcharts-Sequences.md](Flowcharts-Sequences.md)
2. Check Consensus Generation sequence diagram
3. Study attribute definitions in Technical Documentation

---

## 📊 System Overview

### Key Components

| Component | Purpose | Location |
|-----------|---------|----------|
| Proposal Generator | Video processing & keyframe selection | `/proposal_generation_pipeline/` |
| CVAT Integration | Annotation task management | `/processing_pipeline/services/` |
| Quality Service | IAA metrics calculation | `/processing_pipeline/services/` |
| Rule Engine | Validation logic | `/processing_pipeline/services/` |
| Dataset Generator | AVA CSV creation | `/processing_pipeline/services/` |
| Metrics Logger | Performance tracking | `/metrics_logging/` |

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| API | FastAPI | RESTful services |
| UI | Streamlit | Web dashboards |
| Annotation | CVAT | Manual annotation tool |
| Database | PostgreSQL | Data persistence |
| ML Models | RF-DETR, YOLOX | Object detection |
| Cloud | AWS S3 | File storage |
| Container | Docker | Deployment |

### System Metrics

- **Code Volume**: ~15,000+ lines of Python
- **Modules**: 50+ Python files
- **API Endpoints**: 10+ RESTful endpoints
- **UI Dashboards**: 4 Streamlit applications
- **Database Tables**: 4 core tables
- **Action Attributes**: 8 categories, 58 labels

---

## 🛠 Viewing the Diagrams

The Mermaid diagrams in these documents can be rendered in:

- **GitHub/GitLab**: Automatic rendering in markdown
- **VS Code**: Install "Markdown Preview Mermaid Support" extension
- **Mermaid Live Editor**: Copy to https://mermaid.live/
- **Export Options**: SVG, PNG, or PDF formats

---

## 📝 Documentation Standards

### Format Guidelines
- **Markdown**: All documentation in GitHub-flavored markdown
- **Diagrams**: Mermaid for sequence/flow, ASCII art for architecture
- **Code Examples**: Python with syntax highlighting
- **Tables**: For structured data presentation

### Maintenance
- **Version**: 1.0.0
- **Last Updated**: November 2024
- **Update Frequency**: With major releases
- **Review Cycle**: Quarterly

---

## 🔗 Related Resources

### Internal Documentation
- Main README: [`../Readme.md`](../Readme.md)
- Architecture Notes: [`../processing_pipeline/architecture.md`](../processing_pipeline/architecture.md)
- Configuration: [`../processing_pipeline/config/rules.yaml`](../processing_pipeline/config/rules.yaml)

### External Resources
- [CVAT Documentation](https://opencv.github.io/cvat/docs/)
- [AVA Dataset Format](https://research.google.com/ava/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Streamlit Documentation](https://docs.streamlit.io/)

---

## 💡 How to Contribute

### Adding Documentation
1. Follow the existing format and structure
2. Update relevant diagrams if architecture changes
3. Include code examples where applicable
4. Update this README with new sections

### Reporting Issues
1. Create an issue in the project repository
2. Tag with `documentation`
3. Include section and line references

---

## 📞 Support

For questions or clarifications about the documentation:

1. Check the troubleshooting section in Technical Documentation
2. Review relevant sequence diagrams for workflow issues
3. Consult architecture diagrams for system design questions
4. Contact the development team for additional support

---

## 🎓 Learning Path

### Recommended Reading Order

#### **Week 1: Foundation**
1. Executive Summary (Technical Documentation)
2. System Architecture Overview (Architecture Diagrams)
3. Complete End-to-End Workflow (Flowcharts)

#### **Week 2: Deep Dive**
1. Module Documentation (Technical Documentation)
2. Component Architecture (Architecture Diagrams)
3. All Flow Charts (Flowcharts)

#### **Week 3: Advanced**
1. API Reference (Technical Documentation)
2. All Sequence Diagrams (Flowcharts)
3. Database Architecture (Architecture Diagrams)

---

## 📈 Documentation Coverage

| Area | Coverage | Status |
|------|----------|--------|
| System Architecture | 100% | ✅ Complete |
| Module Documentation | 100% | ✅ Complete |
| API Endpoints | 100% | ✅ Complete |
| Workflows | 100% | ✅ Complete |
| Database Schema | 100% | ✅ Complete |
| Deployment | 100% | ✅ Complete |
| Troubleshooting | 90% | ✅ Complete |
| Examples | 85% | ✅ Complete |

---

*This documentation is part of the AVA_Kinetics_QC project - A comprehensive quality control system for action recognition dataset creation.*

*Documentation maintained by the Development Team*
*Version: 1.0.0 | Last Updated: November 2024*