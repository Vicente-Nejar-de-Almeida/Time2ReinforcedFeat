import math
import sys
import gym
import numpy as np
from sklearn.metrics import davies_bouldin_score, calinski_harabasz_score, silhouette_score
from jqmcvi.base import dunn_fast
from early_stopping_class import CustomEarlyStopping


def obtain_score(df_feat_all, y_pred, list_eval):

    scoreTotal = []
    for norm_score in list_eval:
        scoreTotal.append(norm_score.get_normalized_value(df_feat_all, y_pred)[1])
    if math.inf in scoreTotal or -math.inf in scoreTotal:
        raise ValueError
    else:
        score = np.mean(scoreTotal)
        # print("ScoreObtained: ", str(score))
        return score


class FeatureSelectionEnvironment(gym.Env):

    def __init__(self, df_features, n_features, clustering_model, list_eval) -> None:
        self.observation_space = gym.spaces.Box(0, 1, shape=(len(df_features.columns),), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(len(df_features.columns))
        self.all_features = df_features.copy()
        self.current_state = np.zeros(len(self.all_features.columns))
        self.n_features = n_features
        self.clustering_model = clustering_model
        self.custom_early_stopping = CustomEarlyStopping(patience=20, plateau_patience=20)
        self.past_reward = 0
        self.score_history = []
        self.best_conf_feat = []
        self.sum_score = []
        self.list_eval = list_eval
    
    def _get_obs(self) -> np.array:
        return self.current_state

    def _get_info(self) -> dict:
        return {
            'legal_actions': [action for action in range(self.action_space.n) if not self.current_state[action]],
            'score_history': self.score_history,
        }
    
    def reset(self, list_eval, seed=None, options=None):
        self.past_reward = 0
        self.score_history = []
        self.custom_early_stopping = CustomEarlyStopping(patience=20, plateau_patience=20)
        self.current_state = np.zeros(len(self.all_features.columns))
        observation = self._get_obs()
        info = self._get_info()
        self.sum_score = []
        self.list_eval = list_eval
        return observation, info
    
    def _get_reward(self, action):
        selected_features = [feature for i, feature in enumerate(self.all_features.columns) if self.current_state[i]]
        y_pred = self.clustering_model.fit_predict(self.all_features[selected_features])
        try:
            """
            Test to see if this works well, otherwise we have two current options:
            (1) Use only the features selected by RL to compute metrics
            (2) Use raw time series to compute metrics
            """
            score = obtain_score(self.all_features, y_pred, self.list_eval)
            self.sum_score.append(score)
        except ValueError:
            # happens when all labels have same value, thus no real "clustering" has occurred
            score = -1

        gain = score - self.past_reward
        self.past_reward = score

        if len(self.sum_score) == 0:
            sum_score_ins = None
        else:
            sum_score_ins = np.sum(self.sum_score)
        return gain, y_pred, score, selected_features, sum_score_ins
    
    def step(self, action):
        self.current_state[action] = 1
        reward, features, score, features_selected, sum_score = self._get_reward(action)
        observation = self._get_obs()
        info = self._get_info()
        if sum_score is not None:
            checkContinuation = self.custom_early_stopping.update_metric(sum_score)
            if checkContinuation == "Improve":
                self.best_conf_feat = features_selected
                terminated = False
            elif checkContinuation == "Safe":
                terminated = False
            else:
                terminated = True
        else:
            terminated = False

        return observation, reward, terminated, False, info, features_selected
    
    def render(self):
        pass

    def _render_frame(self):
        pass
    
    def close(self):
        pass
