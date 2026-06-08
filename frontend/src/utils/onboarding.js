export const ONBOARDING_TOTAL_XP = 400;

export const ONBOARDING_STEP_KEYS = ['phone', 'delivery', 'collection', 'item'];

function hasPhone(user) {
  const digits = String(user?.phone || '').replace(/\D/g, '');
  return digits.length >= 10;
}

function hasDeliveryPoint(user) {
  return Boolean(user?.delivery_point_code && user?.delivery_point_address);
}

function hasCollection(user) {
  return Number(user?.total_collections || 0) > 0;
}

function hasItem(user) {
  return Number(user?.total_items || 0) > 0;
}

export function getOnboardingSteps(user) {
  const savedSteps = new Set(user?.onboarding_completed_steps || []);
  const phoneDone = savedSteps.has('phone') || hasPhone(user);
  const deliveryDone = savedSteps.has('delivery') || hasDeliveryPoint(user);
  const collectionDone = savedSteps.has('collection') || hasCollection(user);
  const itemDone = savedSteps.has('item') || hasItem(user);

  return [
    {
      key: 'phone',
      number: 1,
      title: 'Связь с доставкой',
      shortTitle: 'Телефон',
      description: 'Заполните номер, чтобы СДЭК мог привязать отправление к участникам сделки.',
      reward: 100,
      done: phoneDone,
      to: '/settings?quest=phone',
      actionLabel: 'Заполнить номер',
    },
    {
      key: 'delivery',
      number: 2,
      title: 'Домашний ПВЗ',
      shortTitle: 'ПВЗ',
      description: 'Выберите пункт выдачи СДЭК, откуда удобно отправлять и получать предметы.',
      reward: 100,
      done: deliveryDone,
      to: '/settings?quest=delivery',
      actionLabel: 'Выбрать ПВЗ',
    },
    {
      key: 'collection',
      number: 3,
      title: 'Первая коллекция',
      shortTitle: 'Коллекция',
      description: 'Создайте витрину для монет, марок, значков или другой темы коллекции.',
      reward: 100,
      done: collectionDone,
      to: '/profile?quest=collection',
      actionLabel: 'Создать коллекцию',
    },
    {
      key: 'item',
      number: 4,
      title: 'Первый экспонат',
      shortTitle: 'Предмет',
      description: 'Добавьте предмет с фото и описанием, чтобы коллекция стала живой.',
      reward: 100,
      done: itemDone,
      locked: !collectionDone && !itemDone,
      lockedLabel: 'Сначала создайте коллекцию',
      to: collectionDone ? '/profile?quest=item' : '/profile?quest=collection',
      actionLabel: collectionDone ? 'Добавить предмет' : 'Открыть коллекцию',
    },
  ];
}

export function getOnboardingProgress(user) {
  const steps = getOnboardingSteps(user);
  const doneCount = steps.filter(step => step.done).length;
  const xp = steps.reduce((sum, step) => sum + (step.done ? step.reward : 0), 0);
  const percent = Math.round((doneCount / steps.length) * 100);
  const nextStep = steps.find(step => !step.done && !step.locked)
    || steps.find(step => !step.done)
    || null;

  const rank = percent === 100
    ? 'Куратор коллекции'
    : percent >= 75
      ? 'Мастер витрины'
      : percent >= 50
        ? 'Хранитель'
        : percent >= 25
          ? 'Стажер'
          : 'Новичок';

  return {
    steps,
    doneCount,
    totalCount: steps.length,
    xp,
    percent,
    rank,
    nextStep,
    complete: doneCount === steps.length,
  };
}
