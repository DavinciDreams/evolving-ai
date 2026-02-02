import Card from '../components/common/Card';
import ChatContainer from '../components/chat/ChatContainer';

const ChatPage = () => {
  return (
    <div className="max-w-7xl mx-auto h-full">
      <Card
        title="Chat with AI Agent"
        className="h-[calc(100vh-12rem)]"
        padding={false}
      >
        <ChatContainer />
      </Card>
    </div>
  );
};

export default ChatPage;
