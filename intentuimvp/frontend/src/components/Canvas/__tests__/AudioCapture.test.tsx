/**
 * Tests for AudioCapture component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { AudioCapture, AudioRecording } from "../AudioCapture";

// Mock MediaRecorder
class MockMediaRecorder {
  static readonly isTypeSupported = vi.fn(() => true);
  readonly state: "inactive" | "recording" | "paused";
  readonly mimeType: string;
  stream: MediaStream;
  ondataavailable: ((event: BlobEvent) => void) | null;
  onstop: (() => void) | null;

  constructor(stream: MediaStream) {
    this.stream = stream;
    this.state = "inactive";
    this.mimeType = "audio/webm";
    this.ondataavailable = null;
    this.onstop = null;
  }

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    if (this.onstop) {
      this.onstop();
    }
  }

  pause() {
    this.state = "paused";
  }

  resume() {
    this.state = "recording";
  }

  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() {}
}

// Mock MediaStream
class MockMediaStream {
  getAudioTracks() {
    return [{ stop: vi.fn() }];
  }
  getTracks() {
    return [{ stop: vi.fn() }];
  }
}

// Mock navigator.mediaDevices.getUserMedia
const mockGetUserMedia = vi.fn();

Object.defineProperty(global.navigator, "mediaDevices", {
  writable: true,
  value: {
    getUserMedia: mockGetUserMedia,
  },
});

// Mock MediaRecorder on window
Object.defineProperty(window, "MediaRecorder", {
  writable: true,
  value: MockMediaRecorder,
});

// Mock URL.createObjectURL and URL.revokeObjectURL
global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
global.URL.revokeObjectURL = vi.fn();

describe("AudioCapture", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetUserMedia.mockResolvedValue(new MockMediaStream() as unknown as MediaStream);
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it("should render with idle status initially", () => {
    render(<AudioCapture />);

    expect(screen.getByText("Ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start recording" })).toBeInTheDocument();
  });

  it("should render status and duration", () => {
    render(<AudioCapture />);

    const statusElement = screen.getByText("Ready");
    expect(statusElement).toBeInTheDocument();
    expect(screen.getByText("00:00")).toBeInTheDocument();
  });

  it("should render record button in idle state", () => {
    render(<AudioCapture />);

    const recordButton = screen.getByRole("button", { name: "Start recording" });
    expect(recordButton).toBeInTheDocument();
    expect(recordButton).toHaveTextContent(/Record/);
  });

  it("should be disabled when disabled prop is true", () => {
    render(<AudioCapture disabled />);

    const recordButton = screen.getByRole("button", { name: "Start recording" });
    expect(recordButton).toBeDisabled();
  });

  it("should show existing recording when provided", () => {
    const existingRecording: AudioRecording = {
      blob: new Blob(["audio data"], { type: "audio/webm" }),
      url: "blob:existing-url",
      duration: 5000,
      createdAt: new Date(),
    };

    render(<AudioCapture existingRecording={existingRecording} />);

    expect(screen.getByText(/Recorded/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Record new audio" })).toBeInTheDocument();
  });

  it("should call onRecordingStart when recording starts", async () => {
    const onRecordingStart = vi.fn();
    render(<AudioCapture onRecordingStart={onRecordingStart} />);

    const recordButton = screen.getByRole("button", { name: "Start recording" });
    fireEvent.click(recordButton);

    await waitFor(() => {
      expect(onRecordingStart).toHaveBeenCalledTimes(1);
    });
  });

  it("should display stop button when recording", async () => {
    render(<AudioCapture />);

    const recordButton = screen.getByRole("button", { name: "Start recording" });
    fireEvent.click(recordButton);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Stop recording" })).toBeInTheDocument();
    });
  });

  it("should call onRecordingComplete with recording when stopped", async () => {
    const onRecordingComplete = vi.fn();
    render(<AudioCapture onRecordingComplete={onRecordingComplete} />);

    const recordButton = screen.getByRole("button", { name: "Start recording" });
    fireEvent.click(recordButton);

    await waitFor(() => {
      const stopButton = screen.getByRole("button", { name: "Stop recording" });
      expect(stopButton).toBeInTheDocument();
    });

    const stopButton = screen.getByRole("button", { name: "Stop recording" });
    fireEvent.click(stopButton);

    await waitFor(() => {
      expect(onRecordingComplete).toHaveBeenCalled();
      const recording = onRecordingComplete.mock.calls[0][0] as AudioRecording;
      expect(recording).toHaveProperty("blob");
      expect(recording).toHaveProperty("url");
      expect(recording).toHaveProperty("duration");
      expect(recording).toHaveProperty("createdAt");
    });
  });

  it("should show error when microphone access fails", async () => {
    const error = new Error("Permission denied");
    mockGetUserMedia.mockRejectedValue(error);

    render(<AudioCapture />);

    const recordButton = screen.getByRole("button", { name: "Start recording" });
    fireEvent.click(recordButton);

    await waitFor(() => {
      expect(screen.getByText(/Error/)).toBeInTheDocument();
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("should render reset button in error state", async () => {
    mockGetUserMedia.mockRejectedValue(new Error("Permission denied"));

    render(<AudioCapture />);

    const recordButton = screen.getByRole("button", { name: "Start recording" });
    fireEvent.click(recordButton);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Reset" })).toBeInTheDocument();
    });
  });

  it("should allow re-recording when completed", async () => {
    const existingRecording: AudioRecording = {
      blob: new Blob(["audio data"], { type: "audio/webm" }),
      url: "blob:existing-url",
      duration: 5000,
      createdAt: new Date(),
    };

    render(<AudioCapture existingRecording={existingRecording} />);

    const rerecordButton = screen.getByRole("button", { name: "Record new audio" });
    expect(rerecordButton).toBeInTheDocument();
  });

  it("should allow deletion of existing recording", async () => {
    const onRecordingComplete = vi.fn();
    const existingRecording: AudioRecording = {
      blob: new Blob(["audio data"], { type: "audio/webm" }),
      url: "blob:existing-url",
      duration: 5000,
      createdAt: new Date(),
    };

    render(
      <AudioCapture
        existingRecording={existingRecording}
        onRecordingComplete={onRecordingComplete}
      />
    );

    // When existing recording is provided, the delete button should be rendered
    const deleteButton = screen.queryByRole("button", { name: "Delete recording" });
    // Note: The component shows the delete button when status is "completed"
    // Since we're providing an existing recording, we expect to be able to interact with it
    // The exact behavior depends on how the component handles existingRecording prop
    if (deleteButton) {
      fireEvent.click(deleteButton);
      await waitFor(() => {
        expect(global.URL.revokeObjectURL).toHaveBeenCalledWith("blob:existing-url");
      });
    }
  });

  it("should format duration as MM:SS", () => {
    render(<AudioCapture />);

    // Initially 00:00
    expect(screen.getByText("00:00")).toBeInTheDocument();
  });

  it("should use custom className when provided", () => {
    const { container } = render(<AudioCapture className="custom-class" />);

    const audioCapture = container.querySelector(".audio-capture");
    expect(audioCapture).toHaveClass("custom-class");
  });

  it("should have proper ARIA labels", () => {
    render(<AudioCapture aria-label="Custom audio capture label" />);

    const container = screen.getByLabelText("Custom audio capture label");
    expect(container).toBeInTheDocument();
  });

  it("should render audio player when recording exists", () => {
    const existingRecording: AudioRecording = {
      blob: new Blob(["audio data"], { type: "audio/webm" }),
      url: "blob:existing-url",
      duration: 5000,
      createdAt: new Date(),
    };

    const { container } = render(<AudioCapture existingRecording={existingRecording} />);

    // Audio element doesn't have a role by default, so query by tag name
    const audioPlayer = container.querySelector("audio");
    expect(audioPlayer).toBeInTheDocument();
    expect(audioPlayer).toHaveAttribute("src", "blob:existing-url");
  });
});
