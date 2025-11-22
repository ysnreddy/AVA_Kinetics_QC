# AVA_Kinetics_QC: Flow Charts and Sequence Diagrams

## Table of Contents

### Flow Charts
1. [Proposal Generation Pipeline Flow](#1-proposal-generation-pipeline-flow)
2. [Task Creation Flow](#2-task-creation-flow)
3. [Annotation Workflow](#3-annotation-workflow)
4. [Quality Control Pipeline Flow](#4-quality-control-pipeline-flow)
5. [Dataset Generation Flow](#5-dataset-generation-flow)
6. [Rule Engine Validation Flow](#6-rule-engine-validation-flow)

### Sequence Diagrams
7. [Complete End-to-End Workflow](#7-complete-end-to-end-workflow)
8. [Pre-Annotation Processing](#8-pre-annotation-processing)
9. [Multi-Annotator Assignment](#9-multi-annotator-assignment)
10. [Post-Annotation Retrieval](#10-post-annotation-retrieval)
11. [Quality Metrics Calculation](#11-quality-metrics-calculation)
12. [Consensus Generation](#12-consensus-generation)
13. [S3 Integration Workflow](#13-s3-integration-workflow)
14. [Error Recovery Flow](#14-error-recovery-flow)

---

## FLOW CHARTS

## 1. Proposal Generation Pipeline Flow

```mermaid
flowchart TD
    Start([Start: Video ZIP Upload]) --> ExtractZIP[Extract ZIP Archive]
    ExtractZIP --> ValidateVideos{Videos Valid?}

    ValidateVideos -->|No| ErrorInvalid[Log Error: Invalid Format]
    ErrorInvalid --> End([End: Failed])

    ValidateVideos -->|Yes| Stage1[Stage 1: Video Preprocessing]

    Stage1 --> RenameFiles[Rename to Standard Format]
    RenameFiles --> ResizeVideo[Resize Videos to 640x480]
    ResizeVideo --> ClipVideo[Clip into Segments]
    ClipVideo --> SaveMetadata[Generate Metadata JSON]

    SaveMetadata --> Stage2[Stage 2: Keyframe Selection]

    Stage2 --> LoadRFDETR[Load RF-DETR Model]
    LoadRFDETR --> ForEachVideo[For Each Video Segment]

    ForEachVideo --> ExtractCandidates[Extract Candidate Frames]
    ExtractCandidates --> RunDetection[Run RF-DETR Detection]
    RunDetection --> ScoreFrames[Score Frames by Quality]

    ScoreFrames --> CalculateMetrics[Calculate Quality Metrics]
    CalculateMetrics --> PersonVisibility[Person Visibility Score]
    CalculateMetrics --> PoseQuality[Pose Quality Score]
    CalculateMetrics --> MotionBlur[Motion Blur Score]

    PersonVisibility --> CombineScores[Weighted Score Combination]
    PoseQuality --> CombineScores
    MotionBlur --> CombineScores

    CombineScores --> SelectBest[Select Best Keyframe]
    SelectBest --> SaveKeyframe[Save Keyframe JPEG]
    SaveKeyframe --> MoreVideos1{More Videos?}

    MoreVideos1 -->|Yes| ForEachVideo
    MoreVideos1 -->|No| Stage3[Stage 3: Person Detection]

    Stage3 --> LoadYOLOX[Load YOLOX Model]
    LoadYOLOX --> LoadByteTracker[Initialize ByteTracker]

    LoadByteTracker --> ForEachKeyframe[For Each Keyframe]
    ForEachKeyframe --> DetectPersons[Detect Persons with YOLOX]
    DetectPersons --> FilterConfidence{Confidence > 0.3?}

    FilterConfidence -->|No| SkipDetection[Skip Low Confidence]
    SkipDetection --> MoreKeyframes1{More Keyframes?}

    FilterConfidence -->|Yes| AssignTrackID[Assign Track ID]
    AssignTrackID --> UpdateTracker[Update ByteTracker State]
    UpdateTracker --> SaveDetection[Save Detection JSON]

    SaveDetection --> MoreKeyframes1
    MoreKeyframes1 -->|Yes| ForEachKeyframe
    MoreKeyframes1 -->|No| Stage4[Stage 4: Proposal Aggregation]

    Stage4 --> LoadAllDetections[Load All Detection JSONs]
    LoadAllDetections --> CreateProposals[Create Dense Proposals]
    CreateProposals --> SerializePickle[Serialize to Pickle]
    SerializePickle --> CreateManifest[Create Keyframe Manifest]

    CreateManifest --> Stage5[Stage 5: Assignment Distribution]

    Stage5 --> LoadAnnotators[Load Annotator List]
    LoadAnnotators --> SetOverlap[Set Overlap Percentage]
    SetOverlap --> GenerateAssignments[Generate Random Assignments]

    GenerateAssignments --> PrimaryAssignment[Assign Primary Annotators]
    PrimaryAssignment --> OverlapAssignment[Assign Overlap Tasks]
    OverlapAssignment --> ValidateDistribution{Distribution Valid?}

    ValidateDistribution -->|No| RegenerateAssign[Regenerate Assignments]
    RegenerateAssign --> GenerateAssignments

    ValidateDistribution -->|Yes| Stage6[Stage 6: Package Creation]

    Stage6 --> ForEachAnnotator[For Each Annotator]
    ForEachAnnotator --> GetAssigned[Get Assigned Keyframes]
    GetAssigned --> CreateZIPPackage[Create Keyframe ZIP]
    CreateZIPPackage --> GenerateXML[Generate CVAT XML]

    GenerateXML --> AddPreAnnotations[Add Pre-Annotations]
    AddPreAnnotations --> SavePackage[Save Package Files]
    SavePackage --> MoreAnnotators{More Annotators?}

    MoreAnnotators -->|Yes| ForEachAnnotator
    MoreAnnotators -->|No| OutputReady[Output Packages Ready]

    OutputReady --> Success([End: Success])
```

## 2. Task Creation Flow

```mermaid
flowchart TD
    Start([Start: User Opens Dashboard]) --> Login[Login to System]
    Login --> AuthCheck{Authenticated?}

    AuthCheck -->|No| ShowError[Show Auth Error]
    ShowError --> Login

    AuthCheck -->|Yes| LoadDashboard[Load Task Creator UI]
    LoadDashboard --> ConfigureCVAT[Configure CVAT Connection]

    ConfigureCVAT --> TestConnection[Test CVAT Connection]
    TestConnection --> ConnSuccess{Connection OK?}

    ConnSuccess -->|No| FixConfig[Fix Configuration]
    FixConfig --> TestConnection

    ConnSuccess -->|Yes| CreateProject[Create New Project]
    CreateProject --> DefineLabels[Define Action Labels]

    DefineLabels --> WalkingBehavior[Walking Behavior Labels]
    DefineLabels --> PhoneUsage[Phone Usage Labels]
    DefineLabels --> SocialInteraction[Social Interaction Labels]
    DefineLabels --> CarryingItems[Carrying Items Labels]
    DefineLabels --> StreetBehavior[Street Behavior Labels]
    DefineLabels --> PostureGesture[Posture/Gesture Labels]
    DefineLabels --> ClothingStyle[Clothing Style Labels]
    DefineLabels --> TimeContext[Time Context Labels]

    WalkingBehavior --> SubmitProject[Submit Project Creation]
    PhoneUsage --> SubmitProject
    SocialInteraction --> SubmitProject
    CarryingItems --> SubmitProject
    StreetBehavior --> SubmitProject
    PostureGesture --> SubmitProject
    ClothingStyle --> SubmitProject
    TimeContext --> SubmitProject

    SubmitProject --> CVATCreateProject[CVAT API: Create Project]
    CVATCreateProject --> ProjectCreated{Success?}

    ProjectCreated -->|No| LogProjectError[Log Error]
    LogProjectError --> CreateProject

    ProjectCreated -->|Yes| GetProjectID[Get Project ID]
    GetProjectID --> UploadPackages[Upload Annotator Packages]

    UploadPackages --> SelectPackage[Select Package ZIP/XML]
    SelectPackage --> ValidatePackage{Package Valid?}

    ValidatePackage -->|No| ShowPackageError[Show Validation Error]
    ShowPackageError --> SelectPackage

    ValidatePackage -->|Yes| CreateTask[Create CVAT Task]
    CreateTask --> UploadFrames[Upload Frame ZIP]
    UploadFrames --> CheckUpload{Upload Success?}

    CheckUpload -->|No| RetryUpload{Retry?}
    RetryUpload -->|Yes| UploadFrames
    RetryUpload -->|No| FailTask[Mark Task Failed]
    FailTask --> MorePackages{More Packages?}

    CheckUpload -->|Yes| ImportXML[Import Pre-Annotations]
    ImportXML --> AssignAnnotator[Assign to Annotator]
    AssignAnnotator --> SaveTaskDB[Save Task to Database]

    SaveTaskDB --> LogMetrics[Log Creation Metrics]
    LogMetrics --> MorePackages

    MorePackages -->|Yes| SelectPackage
    MorePackages -->|No| ShowSummary[Show Creation Summary]

    ShowSummary --> End([End: Tasks Created])
```

## 3. Annotation Workflow

```mermaid
flowchart TD
    Start([Start: Annotator Login]) --> CVATLogin[Login to CVAT]
    CVATLogin --> LoadTasks[Load Assigned Tasks]

    LoadTasks --> SelectTask[Select Task to Annotate]
    SelectTask --> LoadFrames[Load Task Frames]
    LoadFrames --> ShowPreAnnotations[Display Pre-Annotations]

    ShowPreAnnotations --> ReviewFrame[Review Current Frame]
    ReviewFrame --> CheckBoxes{Boxes Correct?}

    CheckBoxes -->|No| AdjustBoxes[Adjust Bounding Boxes]
    AdjustBoxes --> ValidateBox{Box Valid?}

    ValidateBox -->|Area < 1000px| TooSmall[Box Too Small Warning]
    TooSmall --> AdjustBoxes

    ValidateBox -->|Area OK| SaveBox[Save Box Adjustment]
    SaveBox --> AddAttributes

    CheckBoxes -->|Yes| AddAttributes[Add/Edit Attributes]

    AddAttributes --> SelectWalking[Select Walking Behavior]
    SelectWalking --> SelectPhone[Select Phone Usage]
    SelectPhone --> SelectSocial[Select Social Interaction]
    SelectSocial --> SelectCarrying[Select Carrying Items]
    SelectCarrying --> SelectStreet[Select Street Behavior]
    SelectStreet --> SelectPosture[Select Posture/Gesture]
    SelectPosture --> SelectClothing[Select Clothing Style]
    SelectClothing --> SelectTime[Select Time Context]

    SelectTime --> ValidateAttributes{Attributes Valid?}

    ValidateAttributes -->|No| ShowRuleError[Show Validation Error]
    ShowRuleError --> AddAttributes

    ValidateAttributes -->|Yes| SaveAnnotation[Save Frame Annotation]
    SaveAnnotation --> NextFrame{More Frames?}

    NextFrame -->|Yes| ReviewFrame
    NextFrame -->|No| ReviewTask[Review Complete Task]

    ReviewTask --> QualityCheck{Quality OK?}

    QualityCheck -->|No| FixIssues[Fix Identified Issues]
    FixIssues --> ReviewFrame

    QualityCheck -->|Yes| SubmitTask[Submit Task]
    SubmitTask --> UpdateStatus[Update Task Status]
    UpdateStatus --> NotifyComplete[Send Completion Event]

    NotifyComplete --> End([End: Task Completed])
```

## 4. Quality Control Pipeline Flow

```mermaid
flowchart TD
    Start([Start: Task Completed Event]) --> ReceiveWebhook[Receive Webhook]
    ReceiveWebhook --> ParseEvent[Parse Event Data]

    ParseEvent --> ExtractTaskID[Extract Task ID]
    ExtractTaskID --> ExtractAnnotator[Extract Annotator]

    ExtractAnnotator --> Stage1[Stage 1: Export Annotations]

    Stage1 --> RequestExport[Request CVAT Export]
    RequestExport --> PollExport{Export Ready?}

    PollExport -->|No| Wait5Sec[Wait 5 Seconds]
    Wait5Sec --> PollExport

    PollExport -->|Yes| DownloadXML[Download XML]
    DownloadXML --> ParseXML[Parse CVAT XML]

    ParseXML --> Stage2[Stage 2: Rule Validation]

    Stage2 --> LoadRules[Load rules.yaml]
    LoadRules --> ForEachAnnotation[For Each Annotation]

    ForEachAnnotation --> CheckMaxLabels{Labels <= 4?}
    CheckMaxLabels -->|No| FlagOverlabel[Flag: OVERLABEL]
    FlagOverlabel --> NextAnnotation

    CheckMaxLabels -->|Yes| CheckMinArea{Area >= 1000px?}
    CheckMinArea -->|No| BlockTinyBox[Block: TINY_BOX]
    BlockTinyBox --> NextAnnotation

    CheckMinArea -->|Yes| CheckMutualExcl{Check Mutual Exclusivity}
    CheckMutualExcl -->|Violated| BlockMEConflict[Block: ME_CONFLICT]
    BlockMEConflict --> NextAnnotation

    CheckMutualExcl -->|OK| CheckContext{Check Context Rules}
    CheckContext -->|Missing| FlagContextMiss[Flag: CONTEXT_MISS]
    FlagContextMiss --> NextAnnotation

    CheckContext -->|OK| PassValidation[Pass Validation]
    PassValidation --> NextAnnotation[Next Annotation?]

    NextAnnotation -->|Yes| ForEachAnnotation
    NextAnnotation -->|No| Stage3[Stage 3: Store Annotations]

    Stage3 --> ConnectDB[Connect to PostgreSQL]
    ConnectDB --> StoreAnnotations[Store in annotations table]
    StoreAnnotations --> UpdateTaskStatus[Update task status]

    UpdateTaskStatus --> Stage4[Stage 4: Find Partner Task]

    Stage4 --> QueryOverlapGroup[Query Overlap Group]
    QueryOverlapGroup --> PartnerFound{Partner Task?}

    PartnerFound -->|No| MarkSingle[Mark as Single Task]
    MarkSingle --> EndQC

    PartnerFound -->|Yes| CheckPartnerComplete{Partner Complete?}
    CheckPartnerComplete -->|No| WaitPartner[Wait for Partner]
    WaitPartner --> EndQC

    CheckPartnerComplete -->|Yes| Stage5[Stage 5: Calculate Metrics]

    Stage5 --> LoadBothAnnotations[Load Both Annotations]
    LoadBothAnnotations --> MatchFrames[Match Frames]

    MatchFrames --> ForEachFrame[For Each Frame Pair]
    ForEachFrame --> MatchPersons[Match Person Boxes]
    MatchPersons --> CalculateIoU[Calculate IoU]

    CalculateIoU --> StoreFrameIoU[Store Frame IoU]
    StoreFrameIoU --> CompareAttributes[Compare Attributes]
    CompareAttributes --> CalculateKappa[Calculate Cohen's Kappa]

    CalculateKappa --> StoreKappa[Store Kappa Score]
    StoreKappa --> MoreFrames{More Frames?}

    MoreFrames -->|Yes| ForEachFrame
    MoreFrames -->|No| AggregateMetrics[Aggregate Metrics]

    AggregateMetrics --> CalcMeanIoU[Calculate Mean IoU]
    CalcMeanIoU --> CalcMeanKappa[Calculate Mean Kappa]
    CalcMeanKappa --> CalcFlipRate[Calculate Flip Rates]

    CalcFlipRate --> Stage6[Stage 6: Quality Decision]

    Stage6 --> CheckThresholds{IoU >= 0.5 AND Kappa >= 0.6?}

    CheckThresholds -->|Yes| ApproveTask[Approve Task]
    ApproveTask --> UpdateQCStatus[qc_status = 'approved']

    CheckThresholds -->|No| CheckAudit{Random Audit Sample?}
    CheckAudit -->|60% Yes| RouteAdjudication[Route to Adjudication]
    RouteAdjudication --> UpdateQCStatus2[qc_status = 'adjudicate']

    CheckAudit -->|40% No| RejectTask[Reject Task]
    RejectTask --> UpdateQCStatus3[qc_status = 'rejected']

    UpdateQCStatus --> SaveMetrics[Save Quality Metrics]
    UpdateQCStatus2 --> SaveMetrics
    UpdateQCStatus3 --> SaveMetrics

    SaveMetrics --> EndQC([End: QC Complete])
```

## 5. Dataset Generation Flow

```mermaid
flowchart TD
    Start([Start: Generate Dataset Request]) --> SelectProject[Select Project]
    SelectProject --> SetParameters[Set Generation Parameters]

    SetParameters --> Format[Select Format: AVA CSV]
    SetParameters --> ApprovedOnly[Approved Only: Yes/No]
    SetParameters --> ConsensusStrategy[Consensus: Majority Vote]

    Format --> ValidateParams{Parameters Valid?}
    ApprovedOnly --> ValidateParams
    ConsensusStrategy --> ValidateParams

    ValidateParams -->|No| ShowParamError[Show Parameter Error]
    ShowParamError --> SetParameters

    ValidateParams -->|Yes| Stage1[Stage 1: Query Annotations]

    Stage1 --> BuildQuery[Build SQL Query]
    BuildQuery --> FilterApproved{Approved Only?}

    FilterApproved -->|Yes| AddApprovedFilter[Add qc_status = 'approved']
    FilterApproved -->|No| IncludeAll[Include All Completed]

    AddApprovedFilter --> ExecuteQuery[Execute Query]
    IncludeAll --> ExecuteQuery

    ExecuteQuery --> CheckResults{Annotations Found?}
    CheckResults -->|No| NoDataError[Error: No Data]
    NoDataError --> End([End: Failed])

    CheckResults -->|Yes| Stage2[Stage 2: Load Manifest]

    Stage2 --> LoadKeyframeManifest[Load Keyframe Manifest]
    LoadKeyframeManifest --> MapFrameToVideo[Map Frames to Videos]

    MapFrameToVideo --> Stage3[Stage 3: Process Annotations]

    Stage3 --> GroupByVideo[Group by Video ID]
    GroupByVideo --> ForEachVideo[For Each Video]

    ForEachVideo --> SortByTimestamp[Sort by Timestamp]
    SortByTimestamp --> ForEachFrame[For Each Frame]

    ForEachFrame --> GetOverlapAnnotations[Get Overlap Annotations]
    GetOverlapAnnotations --> HasOverlap{Has Overlap?}

    HasOverlap -->|No| UseDirectAnnotation[Use Single Annotation]
    UseDirectAnnotation --> ProcessPerson

    HasOverlap -->|Yes| ApplyConsensus[Apply Consensus Logic]

    ApplyConsensus --> MajorityVote[Majority Vote on Attributes]
    MajorityVote --> AverageBoxes[Average Bounding Boxes]
    AverageBoxes --> WeightByConfidence[Weight by Confidence]

    WeightByConfidence --> ProcessPerson[Process Each Person]

    ProcessPerson --> ExtractBBox[Extract Bounding Box]
    ExtractBBox --> NormalizeCoords[Normalize to [0,1]]
    NormalizeCoords --> ExtractAttributes[Extract Attributes]

    ExtractAttributes --> MapToActionID[Map to Action ID]
    MapToActionID --> FormatRow[Format AVA CSV Row]

    FormatRow --> ValidateRow{Row Valid?}
    ValidateRow -->|No| LogInvalidRow[Log Invalid Row]
    LogInvalidRow --> NextPerson

    ValidateRow -->|Yes| AppendToBuffer[Append to Buffer]
    AppendToBuffer --> NextPerson{More Persons?}

    NextPerson -->|Yes| ProcessPerson
    NextPerson -->|No| NextFrame{More Frames?}

    NextFrame -->|Yes| ForEachFrame
    NextFrame -->|No| NextVideo{More Videos?}

    NextVideo -->|Yes| ForEachVideo
    NextVideo -->|No| Stage4[Stage 4: Finalize Dataset]

    Stage4 --> CreateCSVFile[Create CSV File]
    CreateCSVFile --> AddHeaders[Add AVA Headers]
    AddHeaders --> WriteBuffer[Write Buffer to File]

    WriteBuffer --> ValidateDataset{Dataset Valid?}
    ValidateDataset -->|No| DatasetError[Log Dataset Error]
    DatasetError --> End2([End: Failed])

    ValidateDataset -->|Yes| Stage5[Stage 5: Upload to S3]

    Stage5 --> CheckS3Config{S3 Configured?}
    CheckS3Config -->|No| SaveLocal[Save Locally]
    SaveLocal --> GenerateLocalPath[Generate Local Path]
    GenerateLocalPath --> ReturnPath

    CheckS3Config -->|Yes| GenerateS3Key[Generate S3 Key]
    GenerateS3Key --> UploadToS3[Upload to S3]
    UploadToS3 --> GeneratePresignedURL[Generate Presigned URL]

    GeneratePresignedURL --> ReturnPath[Return Download Path]
    ReturnPath --> LogMetrics[Log Generation Metrics]
    LogMetrics --> Success([End: Dataset Ready])
```

## 6. Rule Engine Validation Flow

```mermaid
flowchart TD
    Start([Start: Annotation Validation]) --> LoadAnnotation[Load Annotation Data]
    LoadAnnotation --> LoadRules[Load rules.yaml]

    LoadRules --> ParseRules[Parse Validation Rules]
    ParseRules --> InitResults[Initialize Validation Results]

    InitResults --> Rule1[Rule 1: Check Label Count]

    Rule1 --> CountActiveLabels[Count Non-'unknown' Labels]
    CountActiveLabels --> CheckMaxLabels{Count <= max_active_labels?}

    CheckMaxLabels -->|No| AddOverlabelFlag[Add OVERLABEL Flag]
    AddOverlabelFlag --> Rule2

    CheckMaxLabels -->|Yes| Rule2[Rule 2: Check Box Area]

    Rule2 --> CalculateArea[Calculate BBox Area]
    CalculateArea --> CheckMinArea{Area >= min_box_area?}

    CheckMinArea -->|No| AddTinyBoxBlock[Add TINY_BOX Block]
    AddTinyBoxBlock --> Rule3

    CheckMinArea -->|Yes| CheckMaxArea{Area <= max_box_area?}
    CheckMaxArea -->|No| AddHugeBoxFlag[Add HUGE_BOX Flag]
    AddHugeBoxFlag --> Rule3

    CheckMaxArea -->|Yes| Rule3[Rule 3: Mutual Exclusivity]

    Rule3 --> GetMEGroups[Get Mutual Exclusivity Groups]
    GetMEGroups --> ForEachMEGroup[For Each ME Group]

    ForEachMEGroup --> CountGroupActive[Count Active in Group]
    CountGroupActive --> CheckMEViolation{Multiple Active?}

    CheckMEViolation -->|Yes| AddMEBlock[Add ME_CONFLICT Block]
    AddMEBlock --> NextMEGroup

    CheckMEViolation -->|No| NextMEGroup{More ME Groups?}
    NextMEGroup -->|Yes| ForEachMEGroup
    NextMEGroup -->|No| Rule4[Rule 4: Context Preconditions]

    Rule4 --> GetContextRules[Get Context Rules]
    GetContextRules --> ForEachAttribute[For Each Attribute]

    ForEachAttribute --> NeedsContext{Requires Context?}
    NeedsContext -->|No| NextAttribute

    NeedsContext -->|Yes| CheckContext[Check Required Context]
    CheckContext --> ContextPresent{Context Found?}

    ContextPresent -->|No| AddContextFlag[Add CONTEXT_MISS Flag]
    AddContextFlag --> NextAttribute

    ContextPresent -->|Yes| NextAttribute{More Attributes?}
    NextAttribute -->|Yes| ForEachAttribute
    NextAttribute -->|No| Rule5[Rule 5: Custom Validations]

    Rule5 --> CheckCustomRules[Apply Custom Rules]
    CheckCustomRules --> AggregateResults[Aggregate All Results]

    AggregateResults --> DetermineAction[Determine Final Action]
    DetermineAction --> HasBlocks{Any Blocks?}

    HasBlocks -->|Yes| BlockAnnotation[Block Annotation]
    BlockAnnotation --> ReturnBlocked

    HasBlocks -->|No| HasFlags{Any Flags?}
    HasFlags -->|Yes| FlagAnnotation[Flag for Review]
    FlagAnnotation --> ReturnFlagged

    HasFlags -->|No| PassAnnotation[Pass Validation]
    PassAnnotation --> ReturnPassed

    ReturnBlocked --> End([End: Validation Complete])
    ReturnFlagged --> End
    ReturnPassed --> End
```

---

## SEQUENCE DIAGRAMS

## 7. Complete End-to-End Workflow

```mermaid
sequenceDiagram
    participant User
    participant UI as Streamlit UI
    participant API as FastAPI
    participant PropGen as Proposal Generator
    participant CVAT
    participant Ann as Annotator
    participant Webhook
    participant PostAnn as Post-Annotation
    participant QC as Quality Service
    participant DB as PostgreSQL
    participant DataGen as Dataset Generator
    participant S3

    User->>UI: Upload video ZIP
    UI->>API: POST /pre-annotation/process
    API->>PropGen: Process videos

    PropGen->>PropGen: Extract & preprocess
    PropGen->>PropGen: Select keyframes
    PropGen->>PropGen: Detect persons
    PropGen->>PropGen: Generate proposals
    PropGen-->>API: Proposals ready

    API-->>UI: Processing complete
    UI-->>User: Show packages ready

    User->>UI: Create tasks
    UI->>API: POST /task-creator/create-project
    API->>CVAT: Create project
    CVAT-->>API: Project ID

    loop For each annotator
        API->>CVAT: Create task
        API->>CVAT: Upload frames
        API->>CVAT: Import XML
        API->>CVAT: Assign user
        API->>DB: Save task metadata
    end

    API-->>UI: Tasks created
    UI-->>User: Show task summary

    Ann->>CVAT: Login & annotate
    Ann->>CVAT: Complete task
    CVAT->>Webhook: Task completed event

    Webhook->>PostAnn: Process completion
    PostAnn->>CVAT: Export annotations
    CVAT-->>PostAnn: XML data
    PostAnn->>PostAnn: Parse & validate
    PostAnn->>DB: Store annotations

    PostAnn->>QC: Trigger quality check
    QC->>DB: Get partner task
    QC->>QC: Calculate metrics
    QC->>DB: Store metrics
    QC-->>PostAnn: QC complete

    User->>UI: Generate dataset
    UI->>API: POST /quality-control/generate-dataset
    API->>DataGen: Generate AVA CSV
    DataGen->>DB: Query annotations
    DataGen->>DataGen: Apply consensus
    DataGen->>S3: Upload dataset
    S3-->>DataGen: S3 URL
    DataGen-->>API: Dataset URL
    API-->>UI: Download link
    UI-->>User: Dataset ready
```

## 8. Pre-Annotation Processing

```mermaid
sequenceDiagram
    participant User
    participant UI as Streamlit UI
    participant API as FastAPI
    participant S3
    participant PropGen as Proposal Generator
    participant Models as ML Models
    participant Storage as File Storage

    User->>UI: Select video files
    UI->>API: Request upload URLs
    API->>S3: Generate presigned URLs
    S3-->>API: Upload URLs
    API-->>UI: Return URLs
    UI-->>User: Show upload interface

    User->>S3: Direct upload videos
    S3-->>User: Upload complete

    User->>UI: Start processing
    UI->>API: POST /pre-annotation/process-clips-s3

    API->>PropGen: Initialize pipeline
    PropGen->>S3: Download videos
    S3-->>PropGen: Video data

    PropGen->>PropGen: Extract videos from ZIP
    PropGen->>PropGen: Rename & resize

    loop For each video
        PropGen->>Models: Load RF-DETR
        Models-->>PropGen: Model ready

        PropGen->>PropGen: Extract frames
        PropGen->>Models: Score frames
        Models-->>PropGen: Quality scores

        PropGen->>PropGen: Select best keyframe
        PropGen->>Storage: Save keyframe
    end

    PropGen->>Models: Load YOLOX
    Models-->>PropGen: Detector ready

    loop For each keyframe
        PropGen->>Models: Detect persons
        Models-->>PropGen: Detections

        PropGen->>Models: Run ByteTracker
        Models-->>PropGen: Track IDs

        PropGen->>Storage: Save detections
    end

    PropGen->>PropGen: Create proposals.pkl
    PropGen->>PropGen: Generate manifest
    PropGen->>Storage: Save outputs

    PropGen-->>API: Processing complete
    API-->>UI: Show results
    UI-->>User: Pre-annotations ready
```

## 9. Multi-Annotator Assignment

```mermaid
sequenceDiagram
    participant Admin
    participant UI
    participant AssignGen as Assignment Generator
    participant DB as PostgreSQL
    participant CVAT

    Admin->>UI: Configure assignment
    Admin->>UI: Set annotators list
    Admin->>UI: Set overlap % (20%)

    UI->>AssignGen: Generate assignments
    Note over AssignGen: Items: 100 clips<br/>Annotators: 3<br/>Overlap: 20%

    AssignGen->>AssignGen: Calculate overlap count
    Note over AssignGen: 100 * 0.2 = 20 overlap clips

    AssignGen->>AssignGen: Shuffle clips randomly
    AssignGen->>AssignGen: Primary assignment round-robin

    Note over AssignGen: Primary Distribution:<br/>Ann1: clips 1,4,7...<br/>Ann2: clips 2,5,8...<br/>Ann3: clips 3,6,9...

    AssignGen->>AssignGen: Select overlap clips
    AssignGen->>AssignGen: Assign secondary annotators

    Note over AssignGen: Overlap Assignment:<br/>20 clips get 2nd annotator<br/>Random selection

    AssignGen->>AssignGen: Validate distribution
    AssignGen-->>UI: Assignment map

    UI->>UI: Display assignment summary
    UI-->>Admin: Review assignments

    Admin->>UI: Approve assignments

    loop For each annotator
        UI->>DB: Create task record
        DB->>DB: Set overlap_group
        DB->>DB: Set partner_task_id

        UI->>CVAT: Create CVAT task
        CVAT-->>UI: Task ID

        UI->>CVAT: Assign to annotator
        UI->>DB: Update task metadata
    end

    UI-->>Admin: Assignments complete
```

## 10. Post-Annotation Retrieval

```mermaid
sequenceDiagram
    participant CVAT
    participant Webhook
    participant PostAnn as Post-Annotation Service
    participant RuleEngine
    participant DB as PostgreSQL
    participant Metrics as Metrics Logger

    CVAT->>Webhook: POST /webhook
    Note over Webhook: Event: update:job<br/>State: completed

    Webhook->>Webhook: Validate event
    Webhook->>Webhook: Extract task_id, annotator

    Webhook->>PostAnn: Process task completion
    activate PostAnn

    PostAnn->>CVAT: Request annotation export
    CVAT-->>PostAnn: Export job ID

    loop Poll for completion
        PostAnn->>CVAT: Check export status
        CVAT-->>PostAnn: Status: processing
        Note over PostAnn: Wait 5 seconds
    end

    CVAT-->>PostAnn: Status: completed
    PostAnn->>CVAT: Download XML
    CVAT-->>PostAnn: CVAT XML data

    PostAnn->>PostAnn: Parse XML structure
    Note over PostAnn: Extract:<br/>- Tracks<br/>- Boxes<br/>- Attributes

    loop For each annotation
        PostAnn->>RuleEngine: Validate annotation

        RuleEngine->>RuleEngine: Check max labels
        RuleEngine->>RuleEngine: Check min area
        RuleEngine->>RuleEngine: Check exclusivity
        RuleEngine->>RuleEngine: Check context

        RuleEngine-->>PostAnn: Validation result

        alt Validation passed
            PostAnn->>DB: Store annotation
        else Validation blocked
            PostAnn->>DB: Store with flag
            PostAnn->>Metrics: Log validation failure
        end
    end

    PostAnn->>DB: Update task status
    PostAnn->>DB: Set retrieved_at timestamp

    PostAnn->>Metrics: Log completion metrics
    deactivate PostAnn

    PostAnn-->>Webhook: Processing complete
    Webhook-->>CVAT: 200 OK
```

## 11. Quality Metrics Calculation

```mermaid
sequenceDiagram
    participant Trigger
    participant QC as Quality Service
    participant DB as PostgreSQL
    participant Routing as Routing Service
    participant Calc as Calculator

    Trigger->>QC: Calculate quality for task

    QC->>DB: Get task info
    DB-->>QC: Task metadata

    QC->>Routing: Find partner task
    Routing->>DB: Query overlap_group
    DB-->>Routing: Partner task_id
    Routing-->>QC: Partner found

    QC->>DB: Check partner status
    DB-->>QC: Status: completed

    QC->>DB: Fetch annotations task 1
    DB-->>QC: Annotations set 1

    QC->>DB: Fetch annotations task 2
    DB-->>QC: Annotations set 2

    QC->>QC: Match frames by name

    loop For each frame pair
        QC->>QC: Match person boxes

        QC->>Calc: Calculate IoU
        Note over Calc: IoU = intersection/union
        Calc-->>QC: IoU score

        QC->>QC: Match attributes

        QC->>Calc: Calculate Kappa
        Note over Calc: κ = (Po - Pe)/(1 - Pe)
        Calc-->>QC: Kappa score
    end

    QC->>QC: Aggregate frame metrics
    Note over QC: Mean IoU: 0.72<br/>Mean Kappa: 0.68

    QC->>Calc: Calculate flip rates
    loop For each track
        Calc->>Calc: Count attribute changes
        Calc->>Calc: Flip rate = changes/frames
    end
    Calc-->>QC: Flip rates

    QC->>QC: Determine quality decision

    alt IoU >= 0.5 AND Kappa >= 0.6
        QC->>DB: Update qc_status = 'approved'
    else Below threshold
        QC->>Routing: Check audit sampling
        Routing->>Routing: Random < 0.6?

        alt Audit sample
            Routing-->>QC: Route to adjudication
            QC->>DB: Update qc_status = 'adjudicate'
        else No audit
            QC->>DB: Update qc_status = 'rejected'
        end
    end

    QC->>DB: Store quality metrics
    QC-->>Trigger: Quality complete
```

## 12. Consensus Generation

```mermaid
sequenceDiagram
    participant DataGen as Dataset Generator
    participant DB as PostgreSQL
    participant Consensus as Consensus Logic
    participant ActionMap as Action Mapper

    DataGen->>DB: Query overlap annotations
    DB-->>DataGen: Overlapping annotation sets

    Note over DataGen: Frame: video_001_frame_042<br/>Annotator 1 & 2 annotations

    DataGen->>Consensus: Apply consensus logic

    Consensus->>Consensus: Group by person track

    loop For each person
        Consensus->>Consensus: Get all boxes

        alt Single annotation
            Consensus->>Consensus: Use directly
        else Multiple annotations
            Consensus->>Consensus: Average bbox coordinates
            Note over Consensus: x = (x1 + x2) / 2<br/>y = (y1 + y2) / 2

            Consensus->>Consensus: Weight by confidence
            Note over Consensus: weighted_x = Σ(x * conf) / Σ(conf)
        end

        Consensus->>Consensus: Get all attributes

        loop For each attribute type
            alt All agree
                Consensus->>Consensus: Use agreed value
            else Disagreement
                Consensus->>Consensus: Majority vote
                Note over Consensus: walking: [normal, normal, fast]<br/>Result: normal (2/3 votes)

                alt No majority
                    Consensus->>Consensus: Use highest confidence
                end
            end
        end
    end

    Consensus-->>DataGen: Consensus annotations

    DataGen->>ActionMap: Map to action IDs

    loop For each annotation
        ActionMap->>ActionMap: Get attribute combination
        Note over ActionMap: {walking: normal,<br/>phone: texting,<br/>carrying: backpack}

        ActionMap->>ActionMap: Lookup action ID
        ActionMap-->>DataGen: Action ID: 42
    end

    DataGen->>DataGen: Format as AVA CSV
    DataGen-->>DB: Store consensus results
```

## 13. S3 Integration Workflow

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI
    participant S3Client as S3 Client
    participant S3 as AWS S3
    participant IAM as IAM Role

    User->>API: Request file upload

    API->>S3Client: Initialize client

    alt Using IAM Role
        S3Client->>IAM: Get credentials
        IAM-->>S3Client: Temporary credentials
    else Using Access Keys
        S3Client->>S3Client: Use configured keys
    end

    API->>S3Client: Generate presigned URL
    S3Client->>S3: Create presigned POST
    S3-->>S3Client: Presigned URL
    S3Client-->>API: Upload URL

    API-->>User: Return upload URL
    Note over User: URL expires in 1 hour

    User->>S3: Direct upload file
    S3->>S3: Validate signature
    S3->>S3: Check permissions
    S3->>S3: Store file
    S3-->>User: Upload success

    User->>API: Process uploaded file
    API->>S3Client: Get object

    S3Client->>S3: GetObject request
    S3->>S3: Check permissions
    S3-->>S3Client: File data
    S3Client-->>API: File content

    API->>API: Process file
    API->>S3Client: Upload results

    S3Client->>S3: PutObject request
    S3->>S3: Store results
    S3-->>S3Client: Success

    API->>S3Client: Generate download URL
    S3Client->>S3: Create presigned GET
    S3-->>S3Client: Download URL
    S3Client-->>API: URL

    API-->>User: Processing complete
    User->>S3: Download results
    S3-->>User: File data
```

## 14. Error Recovery Flow

```mermaid
sequenceDiagram
    participant Service
    participant ErrorHandler
    participant RetryMgr as Retry Manager
    participant DB as PostgreSQL
    participant Logger
    participant Admin

    Service->>Service: Execute operation
    Service->>ErrorHandler: Operation failed

    ErrorHandler->>ErrorHandler: Classify error type

    alt Network error
        ErrorHandler->>RetryMgr: Retryable error

        RetryMgr->>RetryMgr: Check retry count
        Note over RetryMgr: Current: 1/3

        RetryMgr->>RetryMgr: Calculate backoff
        Note over RetryMgr: Wait: 2^1 = 2 seconds

        RetryMgr->>Service: Retry operation

        alt Retry success
            Service-->>ErrorHandler: Success
            ErrorHandler->>Logger: Log recovery
        else Retry failed again
            Service-->>ErrorHandler: Failed
            ErrorHandler->>RetryMgr: Increment count

            alt Under max retries
                RetryMgr->>RetryMgr: Wait 4 seconds
                RetryMgr->>Service: Retry again
            else Max retries exceeded
                RetryMgr->>DB: Mark task failed
                RetryMgr->>Logger: Log failure
                RetryMgr->>Admin: Send alert
            end
        end

    else Database error
        ErrorHandler->>DB: Check connection

        alt Connection lost
            ErrorHandler->>DB: Reconnect
            DB-->>ErrorHandler: Connected
            ErrorHandler->>Service: Retry operation
        else Query error
            ErrorHandler->>Logger: Log SQL error
            ErrorHandler->>DB: Rollback transaction
            ErrorHandler->>Admin: Alert DBA
        end

    else Validation error
        ErrorHandler->>Logger: Log validation details
        ErrorHandler->>DB: Store error record
        ErrorHandler->>Service: Skip item
        ErrorHandler->>Admin: Send report

    else Critical error
        ErrorHandler->>Logger: Log critical
        ErrorHandler->>DB: Emergency save state
        ErrorHandler->>Service: Halt processing
        ErrorHandler->>Admin: Immediate alert
    end

    Logger->>DB: Store error log
    Note over DB: error_logs table:<br/>- timestamp<br/>- service<br/>- error_type<br/>- stack_trace<br/>- recovery_action
```

---

## Flow Chart and Sequence Diagram Summary

This document provides comprehensive flow charts and sequence diagrams for the AVA_Kinetics_QC system:

### Flow Charts (6 diagrams)
1. **Proposal Generation Pipeline** - Complete video processing workflow
2. **Task Creation** - CVAT task setup and configuration
3. **Annotation Workflow** - Annotator interaction flow
4. **Quality Control Pipeline** - Multi-stage quality validation
5. **Dataset Generation** - Consensus and export workflow
6. **Rule Engine Validation** - Detailed validation logic

### Sequence Diagrams (8 diagrams)
1. **End-to-End Workflow** - Complete system interaction
2. **Pre-Annotation Processing** - Video to proposal conversion
3. **Multi-Annotator Assignment** - Task distribution logic
4. **Post-Annotation Retrieval** - Webhook-triggered export
5. **Quality Metrics Calculation** - IAA computation
6. **Consensus Generation** - Multi-annotator agreement
7. **S3 Integration** - Cloud storage workflow
8. **Error Recovery** - Fault tolerance mechanisms

These diagrams visualize:
- **Data transformations** at each stage
- **Decision points** and branching logic
- **Error handling** and recovery paths
- **Service interactions** and dependencies
- **Validation rules** and quality checks

The diagrams use Mermaid syntax for easy rendering in:
- GitHub/GitLab markdown
- VS Code with extensions
- Documentation tools
- Web-based Mermaid editors

---

*Diagrams Version: 1.0.0*
*Last Updated: November 2024*