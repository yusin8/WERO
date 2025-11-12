## gcloud 스크립트

배포/리소스 생성에 필요한 PowerShell 스크립트들입니다.

### 파일
- `bootstrap.ps1` — 프로젝트/리전/존 설정 + 필수 API 활성화
- `create-secret.ps1` — Secret Manager에 `GEMINI_API_KEY` 저장
- `deploy-functions.ps1` — Cloud Functions Gen2 배포(HTTP)
- `deploy-cloudrun.ps1` — Cloud Run 배포(선택)
- `pubsub.ps1` — Pub/Sub 토픽/구독 생성

### 순서 요약
```powershell
./bootstrap.ps1 -ProjectId <PROJECT> -Region <REGION> -Zone <ZONE>
./create-secret.ps1 -ProjectId <PROJECT> -SecretName GEMINI_API_KEY -SecretValue <API_KEY>
./deploy-functions.ps1 -ProjectId <PROJECT> -Region <REGION> -FunctionName ask-gemini
./pubsub.ps1 -ProjectId <PROJECT>
```

