from adapters.outbound.MongoUserRepositoryAdapter import MongoUserRepositoryAdapter
from core.use_cases.UserRecognitionAudioUseCase import (
    UserRecognitionAudioUseCase,
)
from core.use_cases.EnrollUserUseCase import EnrollUserUseCase
from adapters.inbound.RestUserRecognitionAudioAdapter import (
    create_service as create_recognition_service,
)
from adapters.inbound.RestEnrollUserAdapter import create_enrollment_service
from adapters.inbound.RestUserManagementAdapter import create_user_management_service
from fastapi import FastAPI

# Initialize repository
repository = MongoUserRepositoryAdapter()

# Initialize use cases
user_recognition_use_case = UserRecognitionAudioUseCase(repository)
enroll_user_use_case = EnrollUserUseCase(repository)

# Create main app
app = FastAPI(title="Voice Profiling Service")

# Mount sub-applications
recognition_app = create_recognition_service(user_recognition_use_case)
enrollment_app = create_enrollment_service(enroll_user_use_case)
management_app = create_user_management_service(repository)

# Include routers
app.mount("/recognition", recognition_app)
app.mount("/enrollment", enrollment_app)
app.mount("/management", management_app)

@app.get("/")
async def root():
    return {
        "service": "Voice Profiling Service",
        "endpoints": {
            "recognition": "/recognition/recognize_user_by_voice",
            "enrollment": "/enrollment/enroll",
            "users": "/management/users",
            "delete_user": "/management/users/{user_id}"
        }
    }

