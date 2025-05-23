from adapters.outbound.MongoUserRepositoryAdapter import MongoUserRepositoryAdapter
from processing_layer.user_profiling.voice_profiling.core.use_cases.UserRecognitionAudioUseCase import (
    UserRecognitionAudioUseCase,
)
from processing_layer.user_profiling.voice_profiling.adapters.inbound.RestUserRecognitionAudioAdapter import (
    create_service,
)

repository = MongoUserRepositoryAdapter()
user_recognition_use_case = UserRecognitionAudioUseCase(repository)

app = create_service(user_recognition_use_case)
