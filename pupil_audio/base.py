import abc
import typing as T
import numpy as np


EncodedData = T.TypeVar("EncodedData")


DecodedData = np.ndarray


class Codec(T.Generic[EncodedData], abc.ABC):

    @abc.abstractmethod
    def decode(self, data: EncodedData) -> DecodedData:
        pass

    @abc.abstractmethod
    def encode(self, data: DecodedData) -> EncodedData:
        pass


class InputStream(T.Generic[EncodedData], abc.ABC):

    @abc.abstractmethod
    def read_raw(self, chunk_size: int) -> EncodedData:
        pass

    @abc.abstractmethod
    def read_decoded(self, chunk_size: int) -> DecodedData:
        pass

    @abc.abstractmethod
    def close(self):
        pass


class OutputStream(T.Generic[EncodedData], abc.ABC):

    @abc.abstractmethod
    def write_raw(self, data: EncodedData):
        pass

    @abc.abstractmethod
    def write_decoded(self, data: DecodedData):
        pass

    @abc.abstractmethod
    def close(self):
        pass


class StreamWithCodec(abc.ABC):

    @property
    @abc.abstractmethod
    def codec(self) -> Codec:
        pass


class InputStreamWithCodec(T.Generic[EncodedData], InputStream[EncodedData], StreamWithCodec):

    def read_decoded(self, chunk_size: int) -> DecodedData:
        data = self.read_raw(chunk_size=chunk_size)
        data = self.codec.decode(data=data)
        return data


class OutputStreamWithCodec(T.Generic[EncodedData], OutputStream[EncodedData], StreamWithCodec):

    def write_decoded(self, data: DecodedData):
        data = self.codec.encode(data=data)
        self.write_raw(data=data)
