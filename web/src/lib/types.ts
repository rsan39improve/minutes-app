export type QA = {
  質問: string;
  回答: string;
  話者: string;
};

export type Subtopic = {
  番号: string;
  見出し: string;
  説明: string;
  質疑: QA[];
};

export type Topic = {
  番号: string;
  見出し: string;
  小項目: Subtopic[];
};

export type MinutesData = {
  議題: Topic[];
  次回打合せ: string;
};
