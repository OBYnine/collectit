import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Можно прикрутить Sentry: Sentry.captureException(error, { extra: info })
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', error, info);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="min-h-screen flex items-center justify-center px-6 bg-[#0a0e17] text-[#e8eaf0]">
        <div className="max-w-md w-full bg-[#151c2c] border border-white/[.06] rounded-2xl p-8 text-center">
          <div className="text-3xl mb-3">⚠</div>
          <h2 className="text-lg font-bold mb-2">Что-то пошло не так</h2>
          <p className="text-sm text-[#8892a4] mb-5">
            Произошла непредвиденная ошибка. Попробуйте перезагрузить страницу.
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg bg-[#e8a635] text-[#0a0e17] text-sm font-semibold hover:brightness-110 transition"
            >
              Перезагрузить
            </button>
            <button
              onClick={this.handleReset}
              className="px-4 py-2 rounded-lg border border-white/[.12] text-sm text-[#8892a4] hover:text-[#e8eaf0] transition"
            >
              Закрыть
            </button>
          </div>
          {process.env.NODE_ENV === 'development' && (
            <pre className="mt-5 text-[10px] text-left text-[#4a5568] whitespace-pre-wrap overflow-auto max-h-40">
              {String(this.state.error?.stack || this.state.error)}
            </pre>
          )}
        </div>
      </div>
    );
  }
}
