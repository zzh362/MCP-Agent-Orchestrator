from abc import abstractmethod

class ModelInterface:
    @abstractmethod
    async def get_chat_completion(self, messages):
        pass