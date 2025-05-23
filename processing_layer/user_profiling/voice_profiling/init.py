from adapters.outbound.MongoUserRepositoryAdapter import MongoUserRepositoryAdapter
from core.use_cases.UserRecognitionAudioUseCase import (
    UserRecognitionAudioUseCase,
)
from adapters.inbound.RestUserRecognitionAudioAdapter import (
    create_service,
)

repository = MongoUserRepositoryAdapter()
user_recognition_use_case = UserRecognitionAudioUseCase(repository)

app = create_service(user_recognition_use_case)
